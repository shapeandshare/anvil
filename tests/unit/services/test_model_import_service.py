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
        )

    yield maker, _make
    await engine.dispose()


@pytest.mark.asyncio
async def test_import_creates_runnable_model(svc_factory):
    """A Llama-family model resolves to runnable status."""
    maker, make = svc_factory
    async with maker() as session:
        svc = make(session, _FakeSource(arch="LlamaForCausalLM"))
        job_id = await svc.submit_import(source="huggingface", identifier="org/m")
        await svc.run_import(job_id)
        job = await svc.get_job_status(job_id)
        assert job.status == "complete"
        model = await svc.get_external_model(job.external_model_id)
        assert model.runnable_status == "runnable"


@pytest.mark.asyncio
async def test_import_non_allowlist_is_track_only(svc_factory):
    """A non-allow-list architecture resolves to track_only with a reason."""
    maker, make = svc_factory
    async with maker() as session:
        svc = make(session, _FakeSource(arch="Qwen2ForCausalLM"))
        job_id = await svc.submit_import(source="huggingface", identifier="org/q")
        await svc.run_import(job_id)
        job = await svc.get_job_status(job_id)
        model = await svc.get_external_model(job.external_model_id)
        assert model.runnable_status == "track_only"
        assert model.runnable_reason is not None


@pytest.mark.asyncio
async def test_import_idempotent_same_revision(svc_factory):
    """Two imports of the same source+identifier+revision reuse one entry."""
    maker, make = svc_factory
    async with maker() as session:
        svc = make(session, _FakeSource())
        j1 = await svc.submit_import(source="huggingface", identifier="org/m")
        await svc.run_import(j1)
        job1 = await svc.get_job_status(j1)

        j2 = await svc.submit_import(source="huggingface", identifier="org/m")
        await svc.run_import(j2)
        job2 = await svc.get_job_status(j2)

        assert job1.external_model_id == job2.external_model_id
        models = await svc.list_external_models()
        assert len(models) == 1


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
