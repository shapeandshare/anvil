"""Unit tests for ModelImportService catalog registration (US2 T015-T019).

Tests that ``run_import`` registers models in the MLflow Model Catalog
via ``ModelCatalogService`` instead of creating ``ExternalModel`` rows,
and handles dedup, race conditions, and catalog failures.
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from anvil.db.base import Base
from anvil.db.repositories.catalog_identities import CatalogIdentityRepository
from anvil.db.repositories.external_models import ExternalModelRepository
from anvil.db.repositories.model_import_jobs import ModelImportJobRepository
from anvil.services._shared.import_types import ModelMetadata
from anvil.services._shared.source_type import SourceType
from anvil.services.catalog.catalog_unavailable_error import CatalogUnavailableError
from anvil.services.catalog.model_ref import ModelRef
from anvil.services.model_import.model_import_service import ModelImportService


class _FakeCatalogService:
    """Fake ``ModelCatalogService`` for testing."""

    def __init__(self, *, fail: bool = False):
        self._call_count = 0
        self._fail = fail

    async def register_external_model(self, **kwargs) -> ModelRef:
        """Return a deterministic ModelRef."""
        self._call_count += 1
        self._last_kwargs = kwargs
        if self._fail:
            raise CatalogUnavailableError("MLflow is down")
        return ModelRef(name=kwargs["catalog_name"], version=self._call_count)


class _FakeCatalogIdentityRepo:
    """In-memory catalog identity repository for testing."""

    def __init__(self):
        self._rows: list[dict] = []
        self._next_id = 1

    async def find_by_triple(
        self, source_type: str, source_identifier: str, revision_sha: str
    ):
        for row in self._rows:
            if (
                row["source_type"] == source_type
                and row["source_identifier"] == source_identifier
                and row["revision_sha"] == revision_sha
            ):
                return _IdentityRow(**row)
        return None

    async def add(
        self,
        source_type: str,
        source_identifier: str,
        revision_sha: str,
        registry_model_name: str,
    ):
        # Check for duplicates (simulate IntegrityError like the real repo)
        for row in self._rows:
            if (
                row["source_type"] == source_type
                and row["source_identifier"] == source_identifier
                and row["revision_sha"] == revision_sha
            ):
                raise IntegrityError("duplicate", "INSERT ...", {}, ValueError("duplicate"))  # type: ignore[call-arg]
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

    async def set_version(self, identity_id: int, version: int):
        for row in self._rows:
            if row["id"] == identity_id:
                row["registry_model_version"] = version
                return _IdentityRow(**row)
        return None


class _IdentityRow:
    """Simple dict-backed object matching ``CatalogIdentity`` fields."""

    def __init__(self, **kwargs):
        self.id = kwargs.get("id")
        self.source_type = kwargs.get("source_type")
        self.source_identifier = kwargs.get("source_identifier")
        self.revision_sha = kwargs.get("revision_sha")
        self.registry_model_name = kwargs.get("registry_model_name")
        self.registry_model_version = kwargs.get("registry_model_version")


class _FakeSource:
    """Fake ModelSource returning static metadata for tests."""

    name = "huggingface"

    async def resolve_metadata(self, identifier, *, revision="main", token=None):
        return ModelMetadata(
            display_name=identifier,
            architecture_family="LlamaForCausalLM",
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

    def _make(session, catalog_svc, catalog_identity_repo, source):
        return ModelImportService(
            ExternalModelRepository(session),
            ModelImportJobRepository(session),
            {SourceType.HUGGINGFACE: source},
            catalog_service=catalog_svc,
            catalog_identity_repo=catalog_identity_repo,
        )

    yield maker, _make
    await engine.dispose()


@pytest.mark.asyncio
async def test_import_registers_in_catalog(svc_factory):
    """A successful import registers in the catalog and sets registry fields."""
    maker, make = svc_factory
    catalog = _FakeCatalogService()
    identity_repo = _FakeCatalogIdentityRepo()
    async with maker() as session:
        svc = make(session, catalog, identity_repo, _FakeSource())
        job_id = await svc.submit_import(source="huggingface", identifier="org/model")
        await svc.run_import(job_id)
        job = await svc.get_job_status(job_id)

        assert job.status == "complete"
        assert job.registry_model_name is not None
        assert job.registry_model_version is not None
        assert job.external_model_id is None
        assert catalog._call_count == 1


@pytest.mark.asyncio
async def test_import_dedup_same_triple(svc_factory):
    """Two imports of the same source+revision reuse the same registry entry."""
    maker, make = svc_factory
    catalog = _FakeCatalogService()
    identity_repo = _FakeCatalogIdentityRepo()
    async with maker() as session:
        svc = make(session, catalog, identity_repo, _FakeSource())

        j1 = await svc.submit_import(source="huggingface", identifier="org/model")
        await svc.run_import(j1)
        job1 = await svc.get_job_status(j1)

        j2 = await svc.submit_import(source="huggingface", identifier="org/model")
        await svc.run_import(j2)
        job2 = await svc.get_job_status(j2)

        assert job1.registry_model_name == job2.registry_model_name
        assert job1.registry_model_version == job2.registry_model_version
        assert catalog._call_count == 1


@pytest.mark.asyncio
async def test_import_catalog_unavailable(svc_factory):
    """When the catalog service fails, the job is marked failed."""
    maker, make = svc_factory
    catalog = _FakeCatalogService(fail=True)
    identity_repo = _FakeCatalogIdentityRepo()
    async with maker() as session:
        svc = make(session, catalog, identity_repo, _FakeSource())
        job_id = await svc.submit_import(source="huggingface", identifier="org/model")
        await svc.run_import(job_id)
        job = await svc.get_job_status(job_id)

        assert job.status == "failed"
        assert job.error_code == "catalog_unavailable"
        assert job.registry_model_name is None
        assert job.registry_model_version is None


@pytest.mark.asyncio
async def test_import_race_identity_guard(svc_factory):
    """A concurrent insertion race resolves via fallback find_by_triple.

    Pre-inserts an identity row with a known name/version.  The fake
    repo raises ``IntegrityError`` on ``add()`` (simulating a concurrent
    worker that just inserted it), and the fallback ``find_by_triple``
    resolves to the existing row without calling the catalog again.
    """
    from anvil.db.models.catalog_identity import CatalogIdentity

    maker, make = svc_factory
    catalog = _FakeCatalogService()
    identity_repo = _FakeCatalogIdentityRepo()
    async with maker() as session:
        svc = make(session, catalog, identity_repo, _FakeSource())

        # Pre-insert an identity row that matches the import triple,
        # simulating a concurrent worker that already registered the model.
        identity = await identity_repo.add(
            source_type="huggingface",
            source_identifier="org/model",
            revision_sha="resolved-sha",
            registry_model_name="hf--org-model",
        )
        assert identity.id is not None
        await identity_repo.set_version(identity.id, 1)

        job_id = await svc.submit_import(source="huggingface", identifier="org/model")
        await svc.run_import(job_id)
        job = await svc.get_job_status(job_id)

        assert job.status == "complete"
        assert job.registry_model_name == "hf--org-model"
        assert job.registry_model_version == 1
        # register_external_model should NOT have been called — the
        # existing identity row was reused.
        assert catalog._call_count == 0


@pytest.mark.asyncio
async def test_import_list_jobs_includes_registry_fields(svc_factory):
    """list_jobs returns registry_model_name and registry_model_version."""
    maker, make = svc_factory
    catalog = _FakeCatalogService()
    identity_repo = _FakeCatalogIdentityRepo()
    async with maker() as session:
        svc = make(session, catalog, identity_repo, _FakeSource())

        job_id = await svc.submit_import(source="huggingface", identifier="org/model")
        await svc.run_import(job_id)

        jobs = await svc.list_jobs()
        assert len(jobs) >= 1
        for j in jobs:
            if j.id == job_id:
                assert j.registry_model_name is not None
                assert j.registry_model_version is not None


@pytest.mark.asyncio
async def test_import_no_external_model_created(svc_factory):
    """run_import does NOT create ExternalModel rows."""
    maker, make = svc_factory
    catalog = _FakeCatalogService()
    identity_repo = _FakeCatalogIdentityRepo()
    async with maker() as session:
        svc = make(session, catalog, identity_repo, _FakeSource())
        job_id = await svc.submit_import(source="huggingface", identifier="org/model")
        await svc.run_import(job_id)
        job = await svc.get_job_status(job_id)

        assert job.external_model_id is None


@pytest.mark.asyncio
async def test_source_error_still_works(svc_factory):
    """Source errors still mark the job failed (regression)."""
    maker, make = svc_factory

    class _FailingSource:
        name = "huggingface"

        async def resolve_metadata(self, identifier, *, revision="main", token=None):
            from anvil.services._shared.import_types import ModelSourceError

            raise ModelSourceError(code="not_found", message="nope", source=self.name)

    catalog = _FakeCatalogService()
    identity_repo = _FakeCatalogIdentityRepo()
    async with maker() as session:
        svc = make(session, catalog, identity_repo, _FailingSource())
        job_id = await svc.submit_import(source="huggingface", identifier="org/missing")
        await svc.run_import(job_id)
        job = await svc.get_job_status(job_id)

        assert job.status == "failed"
        assert job.error_code == "not_found"
        assert catalog._call_count == 0
