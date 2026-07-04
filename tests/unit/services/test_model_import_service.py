# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for ModelImportService import orchestration."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from anvil.db.base import Base
from anvil.db.repositories.external_models import ExternalModelRepository
from anvil.db.repositories.model_import_jobs import ModelImportJobRepository
from anvil.services._shared.import_types import ModelMetadata, ModelSourceError
from anvil.services._shared.source_type import SourceType
from anvil.services.catalog.model_ref import ModelRef
from anvil.services.model_import.model_import_service import ModelImportService


class _FakeSource:
    """Fake ModelSource returning static metadata for tests."""

    name = "huggingface"

    def __init__(self, *, arch: str = "LlamaForCausalLM", fail: bool = False):
        self._arch = arch
        self._fail = fail

    async def resolve_metadata(self, identifier, *, revision="main", token=None):
        if self._fail:
            raise ModelSourceError(code="not_found", message="nope", source=self.name)
        return ModelMetadata(
            display_name=identifier,
            architecture_family=self._arch,
            parameter_count=1000,
            license="mit",
            tokenizer_family="sentencepiece",
            revision_sha="resolved-sha",
        )


class _FakeCatalogService:
    """Fake ModelCatalogService for testing."""

    def __init__(self):
        self._call_count = 0

    async def register_external_model(self, **kwargs) -> ModelRef:
        self._call_count += 1
        return ModelRef(name=kwargs["catalog_name"], version=self._call_count)


class _FakeCatalogIdentityRepo:
    """In-memory catalog identity repository for testing."""

    def __init__(self):
        self._rows: list[dict] = []
        self._next_id = 1

    async def find_by_triple(self, source_type, source_identifier, revision_sha):
        for row in self._rows:
            if (
                row["source_type"] == source_type
                and row["source_identifier"] == source_identifier
                and row["revision_sha"] == revision_sha
            ):
                return _IdentityRow(**row)
        return None

    async def add(
        self, source_type, source_identifier, revision_sha, registry_model_name
    ):
        row = {
            "id": self._next_id,
            "source_type": source_type,
            "source_identifier": source_identifier,
            "revision_sha": revision_sha,
            "registry_model_name": registry_model_name,
            "registry_model_version": None,
        }
        self._next_id += 1
        self._rows.append(row)
        return _IdentityRow(**row)

    async def set_version(self, identity_id, version):
        for row in self._rows:
            if row["id"] == identity_id:
                row["registry_model_version"] = version
                return _IdentityRow(**row)
        return None

    async def get_model_ref(self, identity_id):
        for row in self._rows:
            if row["id"] == identity_id and row["registry_model_version"] is not None:
                return ModelRef(
                    name=row["registry_model_name"],
                    version=row["registry_model_version"],
                )
        return None


class _IdentityRow:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


@pytest.fixture
async def svc_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    def _make(session, source):
        return ModelImportService(
            ExternalModelRepository(session),
            ModelImportJobRepository(session),
            {SourceType.HUGGINGFACE: source},
            catalog_service=_FakeCatalogService(),
            catalog_identity_repo=_FakeCatalogIdentityRepo(),
        )

    yield maker, _make
    await engine.dispose()


@pytest.mark.asyncio
async def test_import_creates_runnable_model(svc_factory):
    """A Llama-family model registers with registry_model_name/version."""
    maker, make = svc_factory
    async with maker() as session:
        svc = make(session, _FakeSource(arch="LlamaForCausalLM"))
        job_id = await svc.submit_import(source="huggingface", identifier="org/m")
        await svc.run_import(job_id)
        job = await svc.get_job_status(job_id)
        assert job.status == "complete"
        assert job.registry_model_name is not None
        assert job.registry_model_version is not None
        assert job.external_model_id is None


@pytest.mark.asyncio
async def test_import_non_allowlist_is_track_only(svc_factory):
    """A non-allow-list architecture still registers with registry fields."""
    maker, make = svc_factory
    async with maker() as session:
        svc = make(session, _FakeSource(arch="Qwen2ForCausalLM"))
        job_id = await svc.submit_import(source="huggingface", identifier="org/q")
        await svc.run_import(job_id)
        job = await svc.get_job_status(job_id)
        assert job.status == "complete"
        assert job.registry_model_name is not None
        assert job.registry_model_version is not None


@pytest.mark.asyncio
async def test_import_idempotent_same_revision(svc_factory):
    """Two imports of the same source+identifier+revision reuse one catalog entry."""
    maker, make = svc_factory
    async with maker() as session:
        svc = make(session, _FakeSource())
        j1 = await svc.submit_import(source="huggingface", identifier="org/m")
        await svc.run_import(j1)
        job1 = await svc.get_job_status(j1)

        j2 = await svc.submit_import(source="huggingface", identifier="org/m")
        await svc.run_import(j2)
        job2 = await svc.get_job_status(j2)

        assert job1.registry_model_name == job2.registry_model_name
        assert job1.registry_model_version == job2.registry_model_version


@pytest.mark.asyncio
async def test_import_failure_sets_typed_error(svc_factory):
    """A source error marks the job failed with the typed error code."""
    maker, make = svc_factory
    async with maker() as session:
        svc = make(session, _FakeSource(fail=True))
        job_id = await svc.submit_import(source="huggingface", identifier="org/x")
        await svc.run_import(job_id)
        job = await svc.get_job_status(job_id)
        assert job.status == "failed"
        assert job.error_code == "not_found"
        assert job.external_model_id is None


@pytest.mark.asyncio
async def test_submit_unknown_source_raises(svc_factory):
    """Submitting with an unregistered source raises ValueError."""
    maker, make = svc_factory
    async with maker() as session:
        svc = make(session, _FakeSource())
        with pytest.raises(ValueError):
            await svc.submit_import(source="local", identifier="/test/x")


@pytest.mark.asyncio
async def test_list_jobs_returns_all(svc_factory):
    """list_jobs returns all submitted import jobs."""
    maker, make = svc_factory
    async with maker() as session:
        svc = make(session, _FakeSource())
        j1 = await svc.submit_import(source="huggingface", identifier="org/job-a")
        j2 = await svc.submit_import(source="huggingface", identifier="org/job-b")
        jobs = await svc.list_jobs()
        assert len(jobs) >= 2
        ids = {j.id for j in jobs}
        assert j1 in ids
        assert j2 in ids


@pytest.mark.asyncio
async def test_retry_import_creates_new_job(svc_factory):
    """retry_import creates a new job with the same source_identifier."""
    maker, make = svc_factory
    async with maker() as session:
        svc = make(session, _FakeSource(fail=True))
        original_id = await svc.submit_import(
            source="huggingface", identifier="org/retry-me"
        )
        await svc.run_import(original_id)
        original_job = await svc.get_job_status(original_id)
        assert original_job is not None
        assert original_job.status == "failed"

        new_id = await svc.retry_import(original_id)
        assert new_id != original_id

        new_job = await svc.get_job_status(new_id)
        assert new_job is not None
        assert new_job.source_identifier == "org/retry-me"
        assert new_job.status == "queued"


@pytest.mark.asyncio
async def test_retry_missing_job_raises(svc_factory):
    """retry_import on a missing job raises ValueError."""
    maker, make = svc_factory
    async with maker() as session:
        svc = make(session, _FakeSource())
        with pytest.raises(ValueError, match="Import job not found: 9999"):
            await svc.retry_import(9999)
