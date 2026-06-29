# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for content repository API endpoints.

Uses the ``mock_workbench`` / ``override_dep`` pattern
(see test_config.py) to mock all workbench services, enabling
fast, isolated unit tests without a database.

All endpoints are prefixed with ``/v1/content`` per the v1 router
mount at ``/v1``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone, UTC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from anvil.api.app import app
from anvil.api.deps import get_workbench
from anvil.api.v1.content import _injection_queue
from anvil.services.content.ingest_status import IngestStatus
from anvil.services.content.validation_report import ValidationProblem, ValidationReport

pytestmark = pytest.mark.asyncio


# ── Shared datetime for use across mocks ──────────────────────────────

_NOW = datetime.now(UTC)


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def mock_workbench():
    """Create a mocked workbench with all content services as mocks."""
    wb = MagicMock()
    wb.session = AsyncMock()
    wb.session.commit = AsyncMock()
    wb.session.rollback = AsyncMock()

    # Repositories
    wb.content_corpus_repo = MagicMock()
    wb.content_corpus_repo.get = AsyncMock()
    wb.content_corpus_repo.get_all = AsyncMock()
    wb.content_corpus_repo.delete = AsyncMock()

    wb.content_source_repo = MagicMock()
    wb.content_source_repo.get = AsyncMock()
    wb.content_source_repo.get_by_slug = AsyncMock()
    wb.content_source_repo.get_all = AsyncMock()
    wb.content_source_repo.add = AsyncMock()

    wb.content_version_repo = MagicMock()
    wb.content_version_repo.get = AsyncMock()
    wb.content_version_repo.list_by_corpus = AsyncMock()
    wb.content_version_repo.get_entries = AsyncMock()
    wb.content_version_repo.get_run_refs = AsyncMock()

    wb.content_ingest_session_repo = MagicMock()
    wb.content_ingest_session_repo.get = AsyncMock()
    wb.content_ingest_session_repo.get_by_accepted_version = AsyncMock()
    wb.content_ingest_session_repo.list_active = AsyncMock()
    wb.content_ingest_session_repo.update_status = AsyncMock()

    wb.content_lock_repo = MagicMock()
    wb.content_lock_repo.get = AsyncMock()

    # Services
    wb.content_corpora = MagicMock()
    wb.content_corpora.create = AsyncMock()
    wb.content_corpora.tag = AsyncMock()
    wb.content_corpora.revert = AsyncMock()

    wb.content_store = MagicMock()
    wb.content_store.ensure_corpus = AsyncMock()
    wb.content_store.freeze_version = AsyncMock()

    wb.content_ingestion = MagicMock()
    wb.content_ingestion.open_session = AsyncMock()
    wb.content_ingestion.stage = AsyncMock()
    wb.content_ingestion.validate = AsyncMock()
    wb.content_ingestion.accept = AsyncMock()

    wb.content_composition = MagicMock()
    wb.content_composition.preview = AsyncMock()
    wb.content_composition.freeze = AsyncMock()

    wb.content_locks = MagicMock()
    wb.content_locks.list_active = AsyncMock()
    wb.content_locks.acquire = AsyncMock()
    wb.content_locks.release = AsyncMock()

    wb.content_imports = MagicMock()
    wb.content_imports.start = AsyncMock()
    wb.content_imports.list = AsyncMock()
    wb.content_imports.status = AsyncMock()

    return wb


@pytest.fixture
def override_dep(mock_workbench):
    """Override the ``get_workbench`` dependency with the mock."""
    app.dependency_overrides[get_workbench] = lambda: mock_workbench
    yield
    app.dependency_overrides.clear()


# ── Mock object factories ─────────────────────────────────────────────


def _make_mock_corpus(
    id: int = 1,
    slug: str = "test-corpus",
    name: str = "Test Corpus",
    description: str | None = None,
    chunking_strategy: str = "windowed",
    block_size: int = 16,
    chunk_overlap: float = 0.5,
    status: str = "draft",
    created_at: datetime = _NOW,
) -> MagicMock:
    mock = MagicMock()
    mock.id = id
    mock.slug = slug
    mock.name = name
    mock.description = description
    mock.chunking_strategy = chunking_strategy
    mock.block_size = block_size
    mock.chunk_overlap = chunk_overlap
    mock.status = status
    mock.created_at = created_at
    mock.file_count = 0
    mock.document_count = 0
    return mock


def _make_mock_version(
    id: int = 1,
    corpus_id: int = 1,
    version_number: int = 1,
    manifest_digest: str = "abc123",
    label: str | None = None,
    entry_count: int = 0,
    total_bytes: int = 0,
    created_at: datetime = _NOW,
) -> MagicMock:
    mock = MagicMock()
    mock.id = id
    mock.corpus_id = corpus_id
    mock.version_number = version_number
    mock.manifest_digest = manifest_digest
    mock.label = label
    mock.entry_count = entry_count
    mock.total_bytes = total_bytes
    mock.created_at = created_at
    return mock


def _make_mock_entry(
    id: int = 1,
    path: str = "doc.txt",
    content_hash: str = "def456",
    size_bytes: int = 100,
    source_id: int | None = None,
) -> MagicMock:
    mock = MagicMock()
    mock.id = id
    mock.path = path
    mock.content_hash = content_hash
    mock.size_bytes = size_bytes
    mock.source_id = source_id
    return mock


def _make_mock_session(
    id: int = 1,
    corpus_id: int = 1,
    source_id: int = 1,
    status: str = IngestStatus.OPEN,
    staged_entry_count: int = 0,
    problems_json: str | None = None,
    opened_at: datetime = _NOW,
    accepted_version_id: int | None = None,
) -> MagicMock:
    mock = MagicMock()
    mock.id = id
    mock.corpus_id = corpus_id
    mock.source_id = source_id
    mock.status = status
    mock.staged_entry_count = staged_entry_count
    mock.problems_json = problems_json
    mock.opened_at = opened_at
    mock.accepted_version_id = accepted_version_id
    return mock


def _make_mock_source(
    id: int = 1,
    slug: str = "test-source",
    name: str = "Test Source",
    kind: str = "manual",
) -> MagicMock:
    mock = MagicMock()
    mock.id = id
    mock.slug = slug
    mock.name = name
    mock.kind = kind
    return mock


def _make_mock_lock(
    id: int = 1,
    scope: str = "test-scope",
    holder: str = "test-holder",
    state: str = "held",
    acquired_at: datetime = _NOW,
    released_at: datetime | None = None,
) -> MagicMock:
    mock = MagicMock()
    mock.id = id
    mock.scope = scope
    mock.holder = holder
    mock.state = state
    mock.acquired_at = acquired_at
    mock.released_at = released_at
    return mock


def _make_mock_run_ref(
    mlflow_run_id: str = "run_abc123",
    corpus_ref: str = "test-corpus@1",
) -> MagicMock:
    mock = MagicMock()
    mock.mlflow_run_id = mlflow_run_id
    mock.corpus_ref = corpus_ref
    return mock


# ── Helper assertions ─────────────────────────────────────────────────


def _assert_envelope(response_data: dict) -> None:
    """Assert the response has the standard envelope structure."""
    assert "data" in response_data
    assert "error" in response_data
    assert response_data["error"] is None


# ══════════════════════════════════════════════════════════════════════
# Corpora CRUD
# ══════════════════════════════════════════════════════════════════════


class TestCreateCorpus:
    """POST /v1/content/corpora — create a content corpus."""

    async def test_creates_corpus_with_slug(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """A valid creation request returns the corpus data."""
        mock_corpus = _make_mock_corpus(
            id=42, slug="my-corpus", name="My Corpus", description="A test corpus"
        )
        mock_workbench.content_corpora.create.return_value = mock_corpus

        resp = await client.post(
            "/v1/content/corpora",
            json={
                "name": "My Corpus",
                "slug": "my-corpus",
                "description": "A test corpus",
                "chunking_strategy": "windowed",
                "block_size": 16,
                "chunk_overlap": 0.5,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        _assert_envelope(data)
        assert data["data"]["id"] == 42
        assert data["data"]["slug"] == "my-corpus"
        assert data["data"]["name"] == "My Corpus"
        mock_workbench.content_corpora.create.assert_awaited_once()
        mock_workbench.session.commit.assert_awaited_once()

    async def test_creates_corpus_with_auto_slug(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Omitting slug auto-generates one."""
        mock_corpus = _make_mock_corpus(id=2, slug="my-corpus", name="My Corpus")
        mock_workbench.content_corpora.create.return_value = mock_corpus

        resp = await client.post(
            "/v1/content/corpora",
            json={"name": "My Corpus"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == 2

    async def test_returns_422_on_value_error(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """A ValueError from the service yields HTTP 422."""
        mock_workbench.content_corpora.create.side_effect = ValueError("bad corpus")

        resp = await client.post(
            "/v1/content/corpora",
            json={"name": "Bad"},
        )
        assert resp.status_code == 422
        mock_workbench.session.rollback.assert_awaited_once()

    async def test_returns_422_on_missing_name(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Missing required name field yields HTTP 422."""
        resp = await client.post("/v1/content/corpora", json={})
        assert resp.status_code == 422


class TestListCorpora:
    """GET /v1/content/corpora — list all content corpora."""

    async def test_returns_all_corpora(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Returns a list of corpus dicts."""
        mock_workbench.content_corpus_repo.get_all.return_value = [
            _make_mock_corpus(id=1, slug="a", name="A"),
            _make_mock_corpus(id=2, slug="b", name="B"),
        ]

        resp = await client.get("/v1/content/corpora")
        assert resp.status_code == 200
        data = resp.json()
        _assert_envelope(data)
        assert len(data["data"]) == 2
        assert data["data"][0]["slug"] == "a"
        assert data["data"][1]["slug"] == "b"

    async def test_empty_list(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Returns empty list when no corpora exist."""
        mock_workbench.content_corpus_repo.get_all.return_value = []
        resp = await client.get("/v1/content/corpora")
        assert resp.status_code == 200
        assert resp.json()["data"] == []


class TestGetCorpus:
    """GET /v1/content/corpora/{corpus_id} — get single corpus."""

    async def test_returns_corpus(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Returns the matching corpus."""
        mock_workbench.content_corpus_repo.get.return_value = _make_mock_corpus(
            id=7, slug="found", name="Found"
        )
        resp = await client.get("/v1/content/corpora/7")
        assert resp.status_code == 200
        data = resp.json()
        _assert_envelope(data)
        assert data["data"]["id"] == 7

    async def test_returns_404_when_missing(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Non-existent corpus returns 404."""
        mock_workbench.content_corpus_repo.get.return_value = None
        resp = await client.get("/v1/content/corpora/999")
        assert resp.status_code == 404


class TestDeleteCorpus:
    """DELETE /v1/content/corpora/{corpus_id} — delete a corpus."""

    async def test_deletes_corpus(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Successful deletion returns deleted status."""
        mock_workbench.content_corpus_repo.delete.return_value = True
        resp = await client.delete("/v1/content/corpora/1")
        assert resp.status_code == 200
        data = resp.json()
        _assert_envelope(data)
        assert data["data"]["status"] == "deleted"
        mock_workbench.session.commit.assert_awaited_once()

    async def test_returns_404_when_missing(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Deleting non-existent corpus returns 404."""
        mock_workbench.content_corpus_repo.delete.return_value = False
        resp = await client.delete("/v1/content/corpora/999")
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════
# Corpus Versions list
# ══════════════════════════════════════════════════════════════════════


class TestListCorpusVersions:
    """GET /v1/content/corpora/{corpus_id}/versions — list versions."""

    async def test_returns_versions(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Returns list of versions for a corpus."""
        mock_workbench.content_version_repo.list_by_corpus.return_value = [
            _make_mock_version(id=10, corpus_id=1, version_number=1),
            _make_mock_version(id=11, corpus_id=1, version_number=2),
        ]
        resp = await client.get("/v1/content/corpora/1/versions")
        assert resp.status_code == 200
        data = resp.json()
        _assert_envelope(data)
        assert len(data["data"]) == 2
        assert data["data"][0]["version_number"] == 1

    async def test_empty_versions(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Returns empty list when no versions exist."""
        mock_workbench.content_version_repo.list_by_corpus.return_value = []
        resp = await client.get("/v1/content/corpora/1/versions")
        assert resp.status_code == 200
        assert resp.json()["data"] == []


# ══════════════════════════════════════════════════════════════════════
# Sources
# ══════════════════════════════════════════════════════════════════════


class TestCreateSource:
    """POST /v1/content/sources — create a content source."""

    async def test_creates_source(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """A valid source creation returns the source data."""
        mock_source = _make_mock_source(
            id=5, slug="my-source", name="My Source", kind="manual"
        )
        mock_workbench.content_source_repo.add.return_value = mock_source

        resp = await client.post(
            "/v1/content/sources",
            json={"slug": "my-source", "name": "My Source"},
        )
        assert resp.status_code == 200
        data = resp.json()
        _assert_envelope(data)
        assert data["data"]["id"] == 5
        assert data["data"]["slug"] == "my-source"
        assert data["data"]["kind"] == "manual"
        mock_workbench.session.commit.assert_awaited_once()

    async def test_returns_422_on_value_error(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """ValueError from the service yields 422."""
        mock_workbench.content_source_repo.add.side_effect = ValueError("bad source")

        resp = await client.post(
            "/v1/content/sources",
            json={"slug": "bad", "name": "Bad"},
        )
        assert resp.status_code == 422
        mock_workbench.session.rollback.assert_awaited_once()

    async def test_returns_422_on_validation(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Empty slug yields 422."""
        resp = await client.post(
            "/v1/content/sources",
            json={"slug": "", "name": "Bad"},
        )
        assert resp.status_code == 422


class TestListSources:
    """GET /v1/content/sources — list all sources."""

    async def test_returns_sources(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Returns a list of source dicts."""
        mock_workbench.content_source_repo.get_all.return_value = [
            _make_mock_source(id=1, slug="src-a", name="A"),
            _make_mock_source(id=2, slug="src-b", name="B"),
        ]
        resp = await client.get("/v1/content/sources")
        assert resp.status_code == 200
        data = resp.json()
        _assert_envelope(data)
        assert len(data["data"]) == 2

    async def test_empty(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Empty list when no sources exist."""
        mock_workbench.content_source_repo.get_all.return_value = []
        resp = await client.get("/v1/content/sources")
        assert resp.status_code == 200
        assert resp.json()["data"] == []


# ══════════════════════════════════════════════════════════════════════
# Sessions — Open, Stage, Validate, Accept, Abandon, List
# ══════════════════════════════════════════════════════════════════════


class TestOpenSession:
    """POST /v1/content/sessions — open a new ingestion session."""

    async def test_opens_session(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """A valid open-session request returns session data."""
        mock_corpus = _make_mock_corpus(id=1, slug="test-corpus")
        mock_source = _make_mock_source(id=2, slug="test-source")
        mock_workbench.content_corpus_repo.get.return_value = mock_corpus
        mock_workbench.content_source_repo.get_by_slug.return_value = mock_source
        mock_workbench.content_ingestion.open_session.return_value = MagicMock(
            session_id=10
        )
        mock_session = _make_mock_session(
            id=10, corpus_id=1, source_id=2, status="open"
        )
        mock_workbench.content_ingest_session_repo.get.return_value = mock_session

        resp = await client.post(
            "/v1/content/sessions",
            json={"corpus_id": 1, "source": "test-source"},
        )
        assert resp.status_code == 200
        data = resp.json()
        _assert_envelope(data)
        assert data["data"]["id"] == 10
        assert data["data"]["corpus_id"] == 1
        mock_workbench.content_store.ensure_corpus.assert_awaited_once_with(
            "test-corpus"
        )
        mock_workbench.session.commit.assert_awaited_once()

    async def test_returns_404_when_corpus_missing(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Non-existent corpus returns 404."""
        mock_workbench.content_corpus_repo.get.return_value = None
        resp = await client.post(
            "/v1/content/sessions",
            json={"corpus_id": 999, "source": "any"},
        )
        assert resp.status_code == 404

    async def test_returns_404_when_source_missing(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Non-existent source returns 404."""
        mock_workbench.content_corpus_repo.get.return_value = _make_mock_corpus(id=1)
        mock_workbench.content_source_repo.get_by_slug.return_value = None
        resp = await client.post(
            "/v1/content/sessions",
            json={"corpus_id": 1, "source": "nonexistent"},
        )
        assert resp.status_code == 404

    async def test_returns_422_on_value_error(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """ValueError from open_session yields 422."""
        mock_workbench.content_corpus_repo.get.return_value = _make_mock_corpus(id=1)
        mock_workbench.content_source_repo.get_by_slug.return_value = _make_mock_source(
            id=2
        )
        mock_workbench.content_ingestion.open_session.side_effect = ValueError(
            "already open"
        )
        resp = await client.post(
            "/v1/content/sessions",
            json={"corpus_id": 1, "source": "test-source"},
        )
        assert resp.status_code == 422

    async def test_returns_404_when_session_ref_not_found(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """If the created session is not fetchable, return 404."""
        mock_workbench.content_corpus_repo.get.return_value = _make_mock_corpus(id=1)
        mock_workbench.content_source_repo.get_by_slug.return_value = _make_mock_source(
            id=2
        )
        mock_workbench.content_ingestion.open_session.return_value = MagicMock(
            session_id=10
        )
        mock_workbench.content_ingest_session_repo.get.return_value = None
        resp = await client.post(
            "/v1/content/sessions",
            json={"corpus_id": 1, "source": "test-source"},
        )
        assert resp.status_code == 404


class TestStageFile:
    """POST /v1/content/sessions/{session_id}/stage — stage a file."""

    async def test_stages_file(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """A valid file upload returns staged entry data."""
        mock_session = _make_mock_session(
            id=5,
            corpus_id=1,
            source_id=1,
            status=IngestStatus.OPEN,
        )
        mock_workbench.content_ingest_session_repo.get.return_value = mock_session
        mock_workbench.content_ingestion.stage.return_value = MagicMock(
            path="readme.txt",
            content_hash="abc123def456",
            size_bytes=42,
        )

        resp = await client.post(
            "/v1/content/sessions/5/stage?path=readme.txt",
            files={"file": ("readme.txt", b"hello world", "text/plain")},
        )
        assert resp.status_code == 200
        data = resp.json()
        _assert_envelope(data)
        assert data["data"]["path"] == "readme.txt"
        assert data["data"]["content_hash"] == "abc123def456"
        assert data["data"]["size_bytes"] == 42
        mock_workbench.session.commit.assert_awaited_once()

    async def test_returns_404_when_session_missing(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Non-existent session returns 404."""
        mock_workbench.content_ingest_session_repo.get.return_value = None
        resp = await client.post(
            "/v1/content/sessions/999/stage?path=doc.txt",
            files={"file": ("doc.txt", b"data", "text/plain")},
        )
        assert resp.status_code == 404

    async def test_returns_422_when_session_not_open(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Session in non-open status returns 422."""
        mock_session = _make_mock_session(id=5, status=IngestStatus.ACCEPTED)
        mock_workbench.content_ingest_session_repo.get.return_value = mock_session
        resp = await client.post(
            "/v1/content/sessions/5/stage?path=doc.txt",
            files={"file": ("doc.txt", b"data", "text/plain")},
        )
        assert resp.status_code == 422
        assert "not open" in resp.json()["detail"].lower()


class TestValidateSession:
    """POST /v1/content/sessions/{session_id}/validate — validate."""

    async def test_validates_session(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Returns a validation report."""
        mock_session = _make_mock_session(id=5)
        mock_workbench.content_ingest_session_repo.get.return_value = mock_session
        report = ValidationReport(ok=True, problems=[])
        mock_workbench.content_ingestion.validate.return_value = report

        resp = await client.post("/v1/content/sessions/5/validate")
        assert resp.status_code == 200
        data = resp.json()
        _assert_envelope(data)
        assert data["data"]["ok"] is True
        assert data["data"]["problems"] == []
        mock_workbench.session.commit.assert_awaited_once()

    async def test_returns_report_with_problems(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Validation report includes problems."""
        mock_session = _make_mock_session(id=5)
        mock_workbench.content_ingest_session_repo.get.return_value = mock_session
        report = ValidationReport(
            ok=False,
            problems=[
                ValidationProblem(
                    gate_name="size_limit",
                    entry_path="big.txt",
                    reason="Too large",
                    severity="error",
                )
            ],
        )
        mock_workbench.content_ingestion.validate.return_value = report

        resp = await client.post("/v1/content/sessions/5/validate")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["ok"] is False
        assert len(data["problems"]) == 1
        assert data["problems"][0]["gate_name"] == "size_limit"

    async def test_returns_404_when_session_missing(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Non-existent session returns 404."""
        mock_workbench.content_ingest_session_repo.get.return_value = None
        resp = await client.post("/v1/content/sessions/999/validate")
        assert resp.status_code == 404


class TestAcceptSession:
    """POST /v1/content/sessions/{session_id}/accept — accept session."""

    @patch("anvil.api.v1.content._injection_queue")
    async def test_accepts_session(
        self,
        mock_queue: MagicMock,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Accepts session and returns version metadata."""
        mock_session = _make_mock_session(id=5, status=IngestStatus.OPEN)
        mock_workbench.content_ingest_session_repo.get.return_value = mock_session
        mock_workbench.content_ingestion.accept.return_value = MagicMock(
            version_id=100,
            manifest_digest="deadbeef",
            version_number=3,
            entry_count=10,
            total_bytes=5000,
        )

        resp = await client.post("/v1/content/sessions/5/accept")
        assert resp.status_code == 200
        data = resp.json()
        _assert_envelope(data)
        assert data["data"]["version_id"] == 100
        assert data["data"]["version_number"] == 3
        assert data["data"]["entry_count"] == 10
        mock_workbench.session.commit.assert_awaited_once()

    async def test_returns_404_when_session_missing(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Non-existent session returns 404."""
        mock_workbench.content_ingest_session_repo.get.return_value = None
        resp = await client.post("/v1/content/sessions/999/accept")
        assert resp.status_code == 404

    async def test_returns_422_when_status_blocked(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Session in FAILED status returns 422."""
        mock_session = _make_mock_session(id=5, status=IngestStatus.FAILED)
        mock_workbench.content_ingest_session_repo.get.return_value = mock_session
        resp = await client.post("/v1/content/sessions/5/accept")
        assert resp.status_code == 422

    async def test_returns_422_on_value_error(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """ValueError from accept yields 422."""
        mock_session = _make_mock_session(id=5, status=IngestStatus.OPEN)
        mock_workbench.content_ingest_session_repo.get.return_value = mock_session
        mock_workbench.content_ingestion.accept.side_effect = ValueError(
            "validation failed"
        )
        resp = await client.post("/v1/content/sessions/5/accept")
        assert resp.status_code == 422
        mock_workbench.session.rollback.assert_awaited_once()


class TestAbandonSession:
    """POST /v1/content/sessions/{session_id}/abandon — abandon session."""

    async def test_abandons_session(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Abandon marks session as abandoned."""
        mock_session = _make_mock_session(id=5)
        mock_workbench.content_ingest_session_repo.get.return_value = mock_session

        resp = await client.post("/v1/content/sessions/5/abandon")
        assert resp.status_code == 200
        data = resp.json()
        _assert_envelope(data)
        assert data["data"]["status"] == "abandoned"
        mock_workbench.content_ingest_session_repo.update_status.assert_awaited_once_with(
            5, IngestStatus.FAILED
        )
        mock_workbench.session.commit.assert_awaited_once()

    async def test_returns_404_when_session_missing(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Non-existent session returns 404."""
        mock_workbench.content_ingest_session_repo.get.return_value = None
        resp = await client.post("/v1/content/sessions/999/abandon")
        assert resp.status_code == 404


class TestListActiveSessions:
    """GET /v1/content/sessions — list active sessions."""

    async def test_returns_active_sessions(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Returns a list of active sessions."""
        mock_workbench.content_ingest_session_repo.list_active.return_value = [
            _make_mock_session(id=1, corpus_id=1, source_id=1, status="open"),
            _make_mock_session(id=2, corpus_id=1, source_id=2, status="validating"),
        ]
        resp = await client.get("/v1/content/sessions")
        assert resp.status_code == 200
        data = resp.json()
        _assert_envelope(data)
        assert len(data["data"]) == 2

    async def test_empty(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Empty list when no active sessions."""
        mock_workbench.content_ingest_session_repo.list_active.return_value = []
        resp = await client.get("/v1/content/sessions")
        assert resp.status_code == 200
        assert resp.json()["data"] == []


# ══════════════════════════════════════════════════════════════════════
# Versions — Freeze, Get, Tag, Lineage
# ══════════════════════════════════════════════════════════════════════


class TestFreezeVersion:
    """POST /v1/content/corpora/{corpus_id}/freeze — freeze version."""

    async def test_freezes_version(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Freezing creates a new version snapshot."""
        mock_corpus = _make_mock_corpus(id=1, slug="test-corpus")
        mock_workbench.content_corpus_repo.get.return_value = mock_corpus
        mock_workbench.content_store.freeze_version.return_value = MagicMock(
            version_id=42,
            version_number=1,
            manifest_digest="abc",
            label=None,
        )

        resp = await client.post("/v1/content/corpora/1/freeze", json={})
        assert resp.status_code == 200
        data = resp.json()
        _assert_envelope(data)
        assert data["data"]["id"] == 42
        assert data["data"]["version_number"] == 1
        assert data["data"]["corpus_id"] == 1
        mock_workbench.session.commit.assert_awaited_once()

    async def test_returns_404_when_corpus_missing(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Non-existent corpus returns 404."""
        mock_workbench.content_corpus_repo.get.return_value = None
        resp = await client.post("/v1/content/corpora/999/freeze", json={})
        assert resp.status_code == 404

    async def test_freezes_with_label(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Freezing with a label includes it in output."""
        mock_corpus = _make_mock_corpus(id=1, slug="test-corpus")
        mock_workbench.content_corpus_repo.get.return_value = mock_corpus
        mock_workbench.content_store.freeze_version.return_value = MagicMock(
            version_id=42,
            version_number=1,
            manifest_digest="abc",
            label="v1.0",
        )

        resp = await client.post(
            "/v1/content/corpora/1/freeze",
            json={"label": "v1.0"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["label"] == "v1.0"

    async def test_freezes_with_composition(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Freezing with a composition body delegates to
        content_composition.freeze.
        """
        mock_corpus = _make_mock_corpus(id=1, slug="test-corpus")
        mock_workbench.content_corpus_repo.get.return_value = mock_corpus
        mock_workbench.content_composition.freeze.return_value = MagicMock(
            version_id=50,
            version_number=2,
            manifest_digest="comp123",
            label="composed",
        )

        resp = await client.post(
            "/v1/content/corpora/1/freeze",
            json={
                "label": "composed",
                "composition": [{"content_hash": "abc", "weight": 1.0}],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == 50
        mock_workbench.content_composition.freeze.assert_awaited_once()
        mock_workbench.content_store.freeze_version.assert_not_called()

    async def test_composition_freeze_422_on_value_error(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """ValueError from composition.freeze yields 422."""
        mock_corpus = _make_mock_corpus(id=1, slug="test-corpus")
        mock_workbench.content_corpus_repo.get.return_value = mock_corpus
        mock_workbench.content_composition.freeze.side_effect = ValueError(
            "bad composition"
        )
        resp = await client.post(
            "/v1/content/corpora/1/freeze",
            json={
                "composition": [{"content_hash": "bad", "weight": 0.0}],
            },
        )
        assert resp.status_code == 422


class TestGetVersion:
    """GET /v1/content/versions/{version_id} — get version detail."""

    async def test_gets_version_with_entries(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Returns version data including entries."""
        mock_version = _make_mock_version(
            id=10, corpus_id=1, version_number=2, manifest_digest="abc"
        )
        mock_workbench.content_version_repo.get.return_value = mock_version
        mock_workbench.content_version_repo.get_entries.return_value = [
            _make_mock_entry(id=1, path="a.txt", content_hash="h1", size_bytes=100),
            _make_mock_entry(id=2, path="b.txt", content_hash="h2", size_bytes=200),
        ]

        resp = await client.get("/v1/content/versions/10")
        assert resp.status_code == 200
        data = resp.json()
        _assert_envelope(data)
        assert data["data"]["id"] == 10
        assert len(data["data"]["entries"]) == 2
        assert data["data"]["entries"][0]["path"] == "a.txt"

    async def test_returns_404_when_version_missing(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Non-existent version returns 404."""
        mock_workbench.content_version_repo.get.return_value = None
        resp = await client.get("/v1/content/versions/999")
        assert resp.status_code == 404


class TestTagVersion:
    """POST /v1/content/versions/{version_id}/tag — tag a version."""

    async def test_tags_version(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Tags a version successfully."""
        mock_version = _make_mock_version(id=10)
        mock_workbench.content_version_repo.get.return_value = mock_version

        resp = await client.post(
            "/v1/content/versions/10/tag",
            json={"name": "baseline"},
        )
        assert resp.status_code == 200
        data = resp.json()
        _assert_envelope(data)
        assert data["data"]["tag"] == "baseline"
        assert data["data"]["id"] == 10
        mock_workbench.content_corpora.tag.assert_awaited_once_with(10, "baseline")
        mock_workbench.session.commit.assert_awaited_once()

    async def test_returns_404_when_version_missing(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Non-existent version returns 404."""
        mock_workbench.content_version_repo.get.return_value = None
        resp = await client.post(
            "/v1/content/versions/999/tag",
            json={"name": "tag-it"},
        )
        assert resp.status_code == 404

    async def test_returns_409_on_value_error(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """ValueError from tag yields 409 Conflict."""
        mock_version = _make_mock_version(id=10)
        mock_workbench.content_version_repo.get.return_value = mock_version
        mock_workbench.content_corpora.tag.side_effect = ValueError("already tagged")

        resp = await client.post(
            "/v1/content/versions/10/tag",
            json={"name": "dup"},
        )
        assert resp.status_code == 409
        mock_workbench.session.rollback.assert_awaited_once()


class TestGetVersionLineage:
    """GET /v1/content/versions/{version_id}/lineage — get lineage."""

    async def test_returns_lineage(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Returns sources and run_refs for a version."""
        mock_version = _make_mock_version(id=10, corpus_id=1)
        mock_workbench.content_version_repo.get.return_value = mock_version
        mock_workbench.content_version_repo.get_run_refs.return_value = [
            _make_mock_run_ref(mlflow_run_id="run_1", corpus_ref="corpus@1")
        ]
        mock_session = _make_mock_session(accepted_version_id=10, source_id=5)
        mock_workbench.content_ingest_session_repo.get_by_accepted_version.return_value = (
            mock_session
        )
        mock_workbench.content_source_repo.get.return_value = _make_mock_source(
            id=5, slug="test-source", name="Test Source", kind="manual"
        )
        mock_workbench.content_version_repo.get_entries.return_value = []

        resp = await client.get("/v1/content/versions/10/lineage")
        assert resp.status_code == 200
        data = resp.json()
        _assert_envelope(data)
        assert data["data"]["version_id"] == 10
        assert len(data["data"]["sources"]) >= 1
        assert len(data["data"]["run_refs"]) == 1

    async def test_returns_404_when_version_missing(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Non-existent version returns 404."""
        mock_workbench.content_version_repo.get.return_value = None
        resp = await client.get("/v1/content/versions/999/lineage")
        assert resp.status_code == 404

    async def test_lineage_without_session(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Lineage works even when no session accepted the version."""
        mock_version = _make_mock_version(id=10, corpus_id=1)
        mock_workbench.content_version_repo.get.return_value = mock_version
        mock_workbench.content_version_repo.get_run_refs.return_value = []
        mock_workbench.content_ingest_session_repo.get_by_accepted_version.return_value = (
            None
        )
        mock_workbench.content_version_repo.get_entries.return_value = []

        resp = await client.get("/v1/content/versions/10/lineage")
        assert resp.status_code == 200
        assert resp.json()["data"]["sources"] == []


# ══════════════════════════════════════════════════════════════════════
# Composition
# ══════════════════════════════════════════════════════════════════════


class TestCompositionPreview:
    """POST /v1/content/corpora/{corpus_id}/composition/preview."""

    async def test_returns_preview(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Returns composition preview data."""
        mock_corpus = _make_mock_corpus(id=1)
        mock_workbench.content_corpus_repo.get.return_value = mock_corpus
        mock_workbench.content_composition.preview.return_value = {
            "breakdown": [
                {"content_hash": "abc", "weight": 1.0, "bytes": 100, "tokens": 25}
            ]
        }

        resp = await client.post(
            "/v1/content/corpora/1/composition/preview",
            json=[{"content_hash": "abc", "weight": 1.0}],
        )
        assert resp.status_code == 200
        data = resp.json()
        _assert_envelope(data)
        assert "breakdown" in data["data"]

    async def test_returns_404_when_corpus_missing(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Non-existent corpus returns 404."""
        mock_workbench.content_corpus_repo.get.return_value = None
        resp = await client.post(
            "/v1/content/corpora/999/composition/preview",
            json=[{"content_hash": "abc", "weight": 1.0}],
        )
        assert resp.status_code == 404

    async def test_returns_422_on_value_error(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """ValueError from preview yields 422."""
        mock_corpus = _make_mock_corpus(id=1)
        mock_workbench.content_corpus_repo.get.return_value = mock_corpus
        mock_workbench.content_composition.preview.side_effect = ValueError(
            "invalid spec"
        )
        resp = await client.post(
            "/v1/content/corpora/1/composition/preview",
            json=[{"content_hash": "bad", "weight": -1}],
        )
        assert resp.status_code == 422


# ══════════════════════════════════════════════════════════════════════
# Revert
# ══════════════════════════════════════════════════════════════════════


class TestRevertCorpus:
    """POST /v1/content/corpora/{corpus_id}/revert — revert version."""

    async def test_reverts_corpus(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Reverts corpus to a prior version."""
        mock_corpus = _make_mock_corpus(id=1)
        mock_workbench.content_corpus_repo.get.return_value = mock_corpus
        mock_target = _make_mock_version(id=5, corpus_id=1, version_number=2)
        mock_workbench.content_version_repo.get.return_value = mock_target
        mock_workbench.content_corpora.revert.return_value = MagicMock(
            version_id=10,
            version_number=3,
        )

        resp = await client.post(
            "/v1/content/corpora/1/revert",
            json={"to_version_id": 5},
        )
        assert resp.status_code == 200
        data = resp.json()
        _assert_envelope(data)
        assert data["data"]["status"] == "reverted"
        assert data["data"]["new_version_id"] == 10
        assert data["data"]["reverted_to_version"] == 2

    async def test_returns_404_when_corpus_missing(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Non-existent corpus returns 404."""
        mock_workbench.content_corpus_repo.get.return_value = None
        resp = await client.post(
            "/v1/content/corpora/999/revert",
            json={"to_version_id": 1},
        )
        assert resp.status_code == 404

    async def test_returns_404_when_target_missing(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Non-existent target version returns 404."""
        mock_workbench.content_corpus_repo.get.return_value = _make_mock_corpus(id=1)
        mock_workbench.content_version_repo.get.return_value = None
        resp = await client.post(
            "/v1/content/corpora/1/revert",
            json={"to_version_id": 999},
        )
        assert resp.status_code == 404

    async def test_returns_422_when_wrong_corpus(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Target version from different corpus yields 422."""
        mock_workbench.content_corpus_repo.get.return_value = _make_mock_corpus(id=1)
        mock_target = _make_mock_version(id=5, corpus_id=2)
        mock_workbench.content_version_repo.get.return_value = mock_target
        resp = await client.post(
            "/v1/content/corpora/1/revert",
            json={"to_version_id": 5},
        )
        assert resp.status_code == 422

    async def test_returns_422_on_value_error(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """ValueError from revert yields 422."""
        mock_workbench.content_corpus_repo.get.return_value = _make_mock_corpus(id=1)
        mock_target = _make_mock_version(id=5, corpus_id=1)
        mock_workbench.content_version_repo.get.return_value = mock_target
        mock_workbench.content_corpora.revert.side_effect = ValueError("cannot revert")
        resp = await client.post(
            "/v1/content/corpora/1/revert",
            json={"to_version_id": 5},
        )
        assert resp.status_code == 422


# ══════════════════════════════════════════════════════════════════════
# Locking
# ══════════════════════════════════════════════════════════════════════


class TestAcquireLock:
    """POST /v1/content/locks — acquire an advisory lock."""

    async def test_acquires_lock(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Acquires a lock when no conflict exists."""
        mock_workbench.content_locks.list_active.return_value = []
        mock_workbench.content_locks.acquire.return_value = _make_mock_lock(
            id=1, scope="corpus:42", holder="user1"
        )

        resp = await client.post(
            "/v1/content/locks",
            json={"scope": "corpus:42", "holder": "user1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        _assert_envelope(data)
        assert data["data"]["scope"] == "corpus:42"
        assert data["data"]["holder"] == "user1"
        assert data["data"]["state"] == "held"
        mock_workbench.session.commit.assert_awaited_once()

    async def test_returns_409_on_conflict(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Acquiring a lock on an already-held scope returns 409."""
        existing_lock = _make_mock_lock(scope="corpus:42", holder="other")
        mock_workbench.content_locks.list_active.return_value = [existing_lock]

        resp = await client.post(
            "/v1/content/locks",
            json={"scope": "corpus:42", "holder": "me"},
        )
        assert resp.status_code == 409
        mock_workbench.content_locks.acquire.assert_not_called()


class TestReleaseLock:
    """POST /v1/content/locks/{lock_id}/release — release a lock."""

    async def test_releases_lock(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Releases a lock successfully."""
        mock_workbench.content_lock_repo.get.return_value = _make_mock_lock(id=1)

        resp = await client.post("/v1/content/locks/1/release")
        assert resp.status_code == 200
        data = resp.json()
        _assert_envelope(data)
        assert data["data"]["status"] == "released"
        mock_workbench.content_locks.release.assert_awaited_once_with(1)
        mock_workbench.session.commit.assert_awaited_once()

    async def test_returns_404_when_lock_missing(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Non-existent lock returns 404."""
        mock_workbench.content_lock_repo.get.return_value = None
        resp = await client.post("/v1/content/locks/999/release")
        assert resp.status_code == 404


class TestListLocks:
    """GET /v1/content/locks — list active locks."""

    async def test_returns_locks(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Returns list of active locks."""
        mock_workbench.content_locks.list_active.return_value = [
            _make_mock_lock(id=1, scope="s1", holder="h1"),
            _make_mock_lock(id=2, scope="s2", holder="h2"),
        ]
        resp = await client.get("/v1/content/locks")
        assert resp.status_code == 200
        data = resp.json()
        _assert_envelope(data)
        assert len(data["data"]) == 2

    async def test_empty(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Empty list when no locks exist."""
        mock_workbench.content_locks.list_active.return_value = []
        resp = await client.get("/v1/content/locks")
        assert resp.status_code == 200
        assert resp.json()["data"] == []


# ══════════════════════════════════════════════════════════════════════
# Import Jobs
# ══════════════════════════════════════════════════════════════════════


def _make_mock_import_job(
    id: int = 1,
    corpus_id: int = 1,
    source_id: int = 1,
    config_json: str = "{}",
    status: str = IngestStatus.OPEN,
    session_id: int | None = 10,
    message: str | None = None,
    started_at: datetime = _NOW,
    finished_at: datetime | None = None,
) -> MagicMock:
    mock = MagicMock()
    mock.id = id
    mock.corpus_id = corpus_id
    mock.source_id = source_id
    mock.config_json = config_json
    mock.status = status
    mock.session_id = session_id
    mock.message = message
    mock.started_at = started_at
    mock.finished_at = finished_at
    return mock


class TestStartImport:
    """POST /v1/content/imports — start an import job."""

    async def test_starts_import(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Starts an import job and returns its metadata."""
        mock_job = _make_mock_import_job(
            id=42,
            corpus_id=1,
            source_id=2,
            status=IngestStatus.OPEN,
            session_id=10,
        )
        mock_workbench.content_imports.start.return_value = mock_job

        resp = await client.post(
            "/v1/content/imports",
            json={
                "corpus_id": 1,
                "source": "test-source",
                "config": {"key": "value"},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        _assert_envelope(data)
        assert data["data"]["id"] == 42
        assert data["data"]["corpus_id"] == 1
        assert data["data"]["session_id"] == 10
        mock_workbench.session.commit.assert_awaited_once()

    async def test_returns_422_on_value_error(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """ValueError from import start yields 422."""
        mock_workbench.content_imports.start.side_effect = ValueError("bad import")
        resp = await client.post(
            "/v1/content/imports",
            json={
                "corpus_id": 999,
                "source": "bad",
                "config": {},
            },
        )
        assert resp.status_code == 422
        mock_workbench.session.rollback.assert_awaited_once()


class TestListImportJobs:
    """GET /v1/content/imports — list import jobs."""

    async def test_returns_jobs(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Returns a list of import jobs."""
        mock_workbench.content_imports.list.return_value = [
            _make_mock_import_job(id=1),
            _make_mock_import_job(id=2),
        ]
        resp = await client.get("/v1/content/imports")
        assert resp.status_code == 200
        data = resp.json()
        _assert_envelope(data)
        assert len(data["data"]) == 2

    async def test_empty(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Empty list when no import jobs."""
        mock_workbench.content_imports.list.return_value = []
        resp = await client.get("/v1/content/imports")
        assert resp.status_code == 200
        assert resp.json()["data"] == []


class TestGetImportJob:
    """GET /v1/content/imports/{job_id} — get import job status."""

    async def test_returns_job(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Returns a specific import job."""
        mock_job = _make_mock_import_job(id=5, status=IngestStatus.ACCEPTED)
        mock_workbench.content_imports.status.return_value = mock_job

        resp = await client.get("/v1/content/imports/5")
        assert resp.status_code == 200
        data = resp.json()
        _assert_envelope(data)
        assert data["data"]["id"] == 5
        assert data["data"]["status"] == IngestStatus.ACCEPTED

    async def test_returns_404_when_missing(
        self,
        client: AsyncClient,
        mock_workbench: MagicMock,
        override_dep: None,
    ) -> None:
        """Non-existent job returns 404."""
        mock_workbench.content_imports.status.return_value = None
        resp = await client.get("/v1/content/imports/999")
        assert resp.status_code == 404
