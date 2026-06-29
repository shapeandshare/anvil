"""Unit tests for corpus management API endpoints with mocked workbench.

Covers CRUD, fork, ingest, file listing, path analysis, and error paths
using dependency overrides to mock the workbench and tracking service.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from anvil.api.app import app
from anvil.api.deps import get_workbench
from anvil.services.datasets.corpus_scan_result import CorpusScanResult

pytestmark = pytest.mark.asyncio


# ── Mock helpers ───────────────────────────────────────────────────────────


def _make_corpus(
    corpus_id: int = 1,
    name: str = "Test Corpus",
    description: str | None = None,
    root_path: str = "/tmp/test",
    chunking_strategy: str = "windowed",
    chunk_overlap: float = 0.5,
    block_size: int = 16,
    parent_id: int | None = None,
    file_count: int = 0,
    document_count: int = 0,
    language_map: str | None = None,
    errors: str | None = None,
    created_at: datetime | None = None,
) -> MagicMock:
    """Build a mock Corpus ORM instance with the given attributes."""
    c = MagicMock()
    c.id = corpus_id
    c.name = name
    c.description = description
    c.root_path = root_path
    c.chunking_strategy = chunking_strategy
    c.chunk_overlap = chunk_overlap
    c.block_size = block_size
    c.parent_id = parent_id
    c.file_count = file_count
    c.document_count = document_count
    c.language_map = language_map
    c.errors = errors
    c.created_at = created_at or datetime(2026, 1, 1, 12, 0, 0)
    return c


def _make_corpus_file(
    file_id: int = 1,
    corpus_id: int = 1,
    relative_path: str = "test.py",
    language: str | None = "Python",
    line_count: int | None = 10,
    char_count: int | None = 100,
    chunk_count: int | None = 2,
    encoding: str | None = "utf-8",
    size_bytes: int | None = 500,
) -> MagicMock:
    """Build a mock CorpusFile ORM instance with the given attributes."""
    f = MagicMock()
    f.id = file_id
    f.corpus_id = corpus_id
    f.relative_path = relative_path
    f.language = language
    f.line_count = line_count
    f.char_count = char_count
    f.chunk_count = chunk_count
    f.encoding = encoding
    f.size_bytes = size_bytes
    return f


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def mock_workbench():
    """Create a mocked AnvilWorkbench with async session and corpora service."""
    wb = MagicMock()
    wb.corpora = MagicMock()
    wb.session = MagicMock()
    wb.session.commit = AsyncMock()
    wb.session.rollback = AsyncMock()
    return wb


@pytest.fixture
def override_dep(mock_workbench):
    """Override the get_workbench dependency with the mock."""
    app.dependency_overrides[get_workbench] = lambda: mock_workbench
    yield
    app.dependency_overrides.clear()


# ── Create Corpus ──────────────────────────────────────────────────────────


class TestCreateCorpus:
    """Tests for POST /v1/corpora."""

    async def test_create_basic(
        self, client: AsyncClient, mock_workbench, override_dep
    ):
        """Create a corpus with minimal config."""
        mock_corpus = _make_corpus(corpus_id=1, name="My Corpus", root_path="/tmp/test")
        mock_workbench.corpora.create = AsyncMock(return_value=mock_corpus)

        with patch("anvil.api.v1.corpora.tracking_svc") as mock_tracking:
            mock_tracking.start_run = AsyncMock(return_value="run_123")
            mock_tracking.log_corpus_input = AsyncMock()
            mock_tracking.finish_run = AsyncMock()
            mock_tracking.set_tag = AsyncMock()

            r = await client.post(
                "/v1/corpora",
                json={"name": "My Corpus", "root_path": "/tmp/test"},
            )

        assert r.status_code == 200
        data = r.json()["data"]
        assert data["name"] == "My Corpus"
        assert data["id"] == 1
        assert data["chunking_strategy"] == "windowed"
        assert r.json()["error"] is None

    async def test_create_full_config(
        self, client: AsyncClient, mock_workbench, override_dep
    ):
        """Create a corpus with all optional fields."""
        mock_corpus = _make_corpus(
            corpus_id=2,
            name="Full Config",
            root_path="/tmp/test",
            chunking_strategy="file",
            chunk_overlap=0.0,
            block_size=64,
        )
        mock_workbench.corpora.create = AsyncMock(return_value=mock_corpus)

        with patch("anvil.api.v1.corpora.tracking_svc") as mock_tracking:
            mock_tracking.start_run = AsyncMock(return_value="run_456")
            mock_tracking.log_corpus_input = AsyncMock()
            mock_tracking.finish_run = AsyncMock()
            mock_tracking.set_tag = AsyncMock()

            r = await client.post(
                "/v1/corpora",
                json={
                    "name": "Full Config",
                    "root_path": "/tmp/test",
                    "description": "Test description",
                    "chunking_strategy": "file",
                    "chunk_overlap": 0.0,
                    "block_size": 64,
                    "include_patterns": ["*.txt"],
                    "exclude_patterns": ["*.log"],
                },
            )

        assert r.status_code == 200
        data = r.json()["data"]
        assert data["chunking_strategy"] == "file"

    async def test_create_validation_error(
        self, client: AsyncClient, mock_workbench, override_dep
    ):
        """Creating a corpus with invalid data returns 422."""
        mock_workbench.corpora.create = AsyncMock(
            side_effect=ValueError("Invalid path")
        )

        with patch("anvil.api.v1.corpora.tracking_svc"):
            r = await client.post(
                "/v1/corpora",
                json={"name": "Bad", "root_path": "/nonexistent"},
            )

        assert r.status_code == 422
        assert "Invalid path" in r.json()["detail"]

    async def test_create_tracking_degraded(
        self, client: AsyncClient, mock_workbench, override_dep
    ):
        """Corpus creation succeeds even when MLflow tracking returns None."""
        mock_corpus = _make_corpus(corpus_id=1, name="Degraded", root_path="/tmp/test")
        mock_workbench.corpora.create = AsyncMock(return_value=mock_corpus)

        with patch("anvil.api.v1.corpora.tracking_svc") as mock_tracking:
            mock_tracking.start_run = AsyncMock(return_value=None)

            r = await client.post(
                "/v1/corpora",
                json={"name": "Degraded", "root_path": "/tmp/test"},
            )

        assert r.status_code == 200
        assert r.json()["data"]["name"] == "Degraded"

    async def test_create_strips_patterns(
        self, client: AsyncClient, mock_workbench, override_dep
    ):
        """Create corpus strips whitespace from include/exclude patterns."""
        mock_corpus = _make_corpus(corpus_id=1, name="Strip", root_path="/tmp/test")
        mock_workbench.corpora.create = AsyncMock(return_value=mock_corpus)

        with patch("anvil.api.v1.corpora.tracking_svc") as mock_tracking:
            mock_tracking.start_run = AsyncMock(return_value="run_1")
            mock_tracking.log_corpus_input = AsyncMock()
            mock_tracking.finish_run = AsyncMock()
            mock_tracking.set_tag = AsyncMock()

            r = await client.post(
                "/v1/corpora",
                json={
                    "name": "Strip",
                    "root_path": "/tmp/test",
                    "include_patterns": ["  *.py ", " *.md"],
                    "exclude_patterns": ["  *.log  "],
                },
            )

        assert r.status_code == 200


# ── List Corpora ──────────────────────────────────────────────────────────


class TestListCorpora:
    """Tests for GET /v1/corpora."""

    async def test_list_corpora(
        self, client: AsyncClient, mock_workbench, override_dep
    ):
        """List all corpora."""
        c1 = _make_corpus(corpus_id=1, name="Corpus A")
        c2 = _make_corpus(corpus_id=2, name="Corpus B")
        mock_workbench.corpora.list_all = AsyncMock(return_value=[c1, c2])

        r = await client.get("/v1/corpora")

        assert r.status_code == 200
        data = r.json()["data"]
        assert len(data) == 2
        assert data[0]["name"] == "Corpus A"
        assert data[1]["name"] == "Corpus B"
        assert r.json()["error"] is None

    async def test_list_empty(self, client: AsyncClient, mock_workbench, override_dep):
        """List corpora when none exist returns empty list."""
        mock_workbench.corpora.list_all = AsyncMock(return_value=[])

        r = await client.get("/v1/corpora")

        assert r.status_code == 200
        assert r.json()["data"] == []


# ── Get Corpus ────────────────────────────────────────────────────────────


class TestGetCorpus:
    """Tests for GET /v1/corpora/{corpus_id}."""

    async def test_get_corpus(self, client: AsyncClient, mock_workbench, override_dep):
        """Get a single corpus by ID."""
        mock_corpus = _make_corpus(corpus_id=1, name="Get-It")
        mock_workbench.corpora.get = AsyncMock(return_value=mock_corpus)

        r = await client.get("/v1/corpora/1")

        assert r.status_code == 200
        assert r.json()["data"]["name"] == "Get-It"

    async def test_get_corpus_not_found(
        self, client: AsyncClient, mock_workbench, override_dep
    ):
        """Getting a non-existent corpus returns 404."""
        mock_workbench.corpora.get = AsyncMock(return_value=None)

        r = await client.get("/v1/corpora/99999")

        assert r.status_code == 404
        assert "Corpus not found" in r.json()["detail"]

    async def test_get_corpus_with_language_map(
        self, client: AsyncClient, mock_workbench, override_dep
    ):
        """Get corpus parses language_map JSON."""
        mock_corpus = _make_corpus(
            corpus_id=1,
            name="Lang",
            language_map='{"Python": 5, "Markdown": 2}',
        )
        mock_workbench.corpora.get = AsyncMock(return_value=mock_corpus)

        r = await client.get("/v1/corpora/1")

        assert r.status_code == 200
        data = r.json()["data"]
        assert data["language_map"] == {"Python": 5, "Markdown": 2}

    async def test_get_corpus_with_invalid_language_map(
        self, client: AsyncClient, mock_workbench, override_dep
    ):
        """Get corpus returns None language_map when JSON is invalid."""
        mock_corpus = _make_corpus(
            corpus_id=1,
            name="BadLang",
            language_map="not json",
        )
        mock_workbench.corpora.get = AsyncMock(return_value=mock_corpus)

        r = await client.get("/v1/corpora/1")

        assert r.status_code == 200
        assert r.json()["data"]["language_map"] is None

    async def test_get_corpus_with_errors(
        self, client: AsyncClient, mock_workbench, override_dep
    ):
        """Get corpus parses errors JSON."""
        mock_corpus = _make_corpus(
            corpus_id=1,
            name="Err",
            errors='["File not found", "Parse error"]',
        )
        mock_workbench.corpora.get = AsyncMock(return_value=mock_corpus)

        r = await client.get("/v1/corpora/1")

        assert r.status_code == 200
        data = r.json()["data"]
        assert data["errors"] == ["File not found", "Parse error"]

    async def test_get_corpus_with_malformed_errors(
        self, client: AsyncClient, mock_workbench, override_dep
    ):
        """Get corpus silently ignores malformed errors JSON."""
        mock_corpus = _make_corpus(
            corpus_id=1,
            name="BadErr",
            errors="not json",
        )
        mock_workbench.corpora.get = AsyncMock(return_value=mock_corpus)

        r = await client.get("/v1/corpora/1")

        assert r.status_code == 200
        assert "errors" not in r.json()["data"]


# ── Delete Corpus ─────────────────────────────────────────────────────────


class TestDeleteCorpus:
    """Tests for DELETE /v1/corpora/{corpus_id}."""

    @staticmethod
    def _patch_tracking():
        """Patch TrackingService inside delete_corpus so it doesn't
        attempt to connect to MLflow (which would hang without a server).
        """
        mock_tracking_instance = MagicMock()
        mock_tracking_instance.is_degraded = True
        return patch(
            "anvil.api.v1.corpora.TrackingService", return_value=mock_tracking_instance
        )

    async def test_delete_corpus(
        self, client: AsyncClient, mock_workbench, override_dep
    ):
        """Delete an existing corpus."""
        mock_workbench.corpora.delete = AsyncMock(return_value=True)

        with self._patch_tracking():
            r = await client.delete("/v1/corpora/1")

        assert r.status_code == 200
        assert r.json()["data"]["status"] == "deleted"
        assert r.json()["error"] is None

    async def test_delete_corpus_not_found(
        self, client: AsyncClient, mock_workbench, override_dep
    ):
        """Delete a non-existent corpus returns 404."""
        mock_workbench.corpora.delete = AsyncMock(return_value=False)

        with self._patch_tracking():
            r = await client.delete("/v1/corpora/99999")

        assert r.status_code == 404


# ── Fork Corpus ────────────────────────────────────────────────────────────


class TestForkCorpus:
    """Tests for POST /v1/corpora/{corpus_id}/fork."""

    async def test_fork_corpus(self, client: AsyncClient, mock_workbench, override_dep):
        """Fork a corpus."""
        forked = _make_corpus(
            corpus_id=2,
            name="Forked",
            parent_id=1,
        )
        mock_workbench.corpora.fork = AsyncMock(return_value=forked)

        with patch("anvil.api.v1.corpora.tracking_svc") as mock_tracking:
            mock_tracking.start_run = AsyncMock(return_value="run_fork")
            mock_tracking.log_corpus_input = AsyncMock()
            mock_tracking.finish_run = AsyncMock()
            mock_tracking.set_tag = AsyncMock()

            r = await client.post(
                "/v1/corpora/1/fork",
                json={"name": "Forked"},
            )

        assert r.status_code == 200
        data = r.json()["data"]
        assert data["name"] == "Forked"
        assert data["parent_id"] == 1
        assert data["id"] == 2

    async def test_fork_corpus_not_found(
        self, client: AsyncClient, mock_workbench, override_dep
    ):
        """Fork a non-existent corpus returns 422."""
        mock_workbench.corpora.fork = AsyncMock(
            side_effect=ValueError("Source corpus not found")
        )

        with patch("anvil.api.v1.corpora.tracking_svc"):
            r = await client.post(
                "/v1/corpora/99999/fork",
                json={"name": "Orphan"},
            )

        assert r.status_code == 422

    async def test_fork_with_overrides(
        self, client: AsyncClient, mock_workbench, override_dep
    ):
        """Fork a corpus with chunking strategy overrides."""
        forked = _make_corpus(
            corpus_id=3,
            name="Forked-Overrides",
            parent_id=1,
            chunking_strategy="line",
        )
        mock_workbench.corpora.fork = AsyncMock(return_value=forked)

        with patch("anvil.api.v1.corpora.tracking_svc") as mock_tracking:
            mock_tracking.start_run = AsyncMock(return_value="run_fork2")
            mock_tracking.log_corpus_input = AsyncMock()
            mock_tracking.finish_run = AsyncMock()
            mock_tracking.set_tag = AsyncMock()

            r = await client.post(
                "/v1/corpora/1/fork",
                json={
                    "name": "Forked-Overrides",
                    "chunking_strategy": "line",
                    "chunk_overlap": 0.25,
                    "block_size": 32,
                },
            )

        assert r.status_code == 200
        assert r.json()["data"]["chunking_strategy"] == "line"


# ── Ingest Corpus ──────────────────────────────────────────────────────────


class TestIngestCorpus:
    """Tests for POST /v1/corpora/{corpus_id}/ingest."""

    async def test_ingest_corpus(
        self, client: AsyncClient, mock_workbench, override_dep
    ):
        """Ingest files from a corpus."""
        ingested = _make_corpus(
            corpus_id=1,
            name="Ingest-Me",
            file_count=3,
            document_count=15,
            language_map='{"Python": 3}',
        )
        mock_workbench.corpora.ingest = AsyncMock(return_value=(ingested, []))

        with patch("anvil.api.v1.corpora.tracking_svc") as mock_tracking:
            mock_tracking.start_run = AsyncMock(return_value="run_ingest")
            mock_tracking.log_corpus_input = AsyncMock()
            mock_tracking.finish_run = AsyncMock()
            mock_tracking.set_tag = AsyncMock()

            r = await client.post("/v1/corpora/1/ingest")

        assert r.status_code == 200
        data = r.json()["data"]
        assert data["corpus_id"] == 1
        assert data["file_count"] == 3
        assert data["document_count"] == 15
        assert data["language_map"] == {"Python": 3}
        assert data["errors"] == []

    async def test_ingest_corpus_not_found(
        self, client: AsyncClient, mock_workbench, override_dep
    ):
        """Ingest a non-existent corpus returns 422."""
        mock_workbench.corpora.ingest = AsyncMock(
            side_effect=ValueError("Corpus not found")
        )

        r = await client.post("/v1/corpora/99999/ingest")

        assert r.status_code == 422

    async def test_ingest_not_a_directory(
        self, client: AsyncClient, mock_workbench, override_dep
    ):
        """Ingest with invalid path returns 422."""
        mock_workbench.corpora.ingest = AsyncMock(
            side_effect=NotADirectoryError("Not a directory")
        )

        r = await client.post("/v1/corpora/1/ingest")

        assert r.status_code == 422

    async def test_ingest_with_max_files(
        self, client: AsyncClient, mock_workbench, override_dep
    ):
        """Ingest with max_files parameter."""
        ingested = _make_corpus(
            corpus_id=1,
            name="Max",
            file_count=2,
            document_count=10,
        )
        mock_workbench.corpora.ingest = AsyncMock(return_value=(ingested, []))

        with patch("anvil.api.v1.corpora.tracking_svc") as mock_tracking:
            mock_tracking.start_run = AsyncMock(return_value="run_max")
            mock_tracking.log_corpus_input = AsyncMock()
            mock_tracking.finish_run = AsyncMock()
            mock_tracking.set_tag = AsyncMock()

            r = await client.post("/v1/corpora/1/ingest?max_files=2")

        assert r.status_code == 200
        mock_workbench.corpora.ingest.assert_called_with(1, 2)


# ── List & Get Corpus Files ────────────────────────────────────────────────


class TestListCorpusFiles:
    """Tests for GET /v1/corpora/{corpus_id}/files."""

    async def test_list_files(self, client: AsyncClient, mock_workbench, override_dep):
        """List files in a corpus."""
        f1 = _make_corpus_file(file_id=1, corpus_id=1, relative_path="a.py")
        f2 = _make_corpus_file(file_id=2, corpus_id=1, relative_path="b.py")
        mock_workbench.corpora.get_files = AsyncMock(return_value=[f1, f2])

        r = await client.get("/v1/corpora/1/files")

        assert r.status_code == 200
        files = r.json()["data"]
        assert len(files) == 2
        assert files[0]["relative_path"] == "a.py"
        assert files[1]["relative_path"] == "b.py"

    async def test_list_files_empty(
        self, client: AsyncClient, mock_workbench, override_dep
    ):
        """List files when none exist returns empty list."""
        mock_workbench.corpora.get_files = AsyncMock(return_value=[])

        r = await client.get("/v1/corpora/1/files")

        assert r.status_code == 200
        assert r.json()["data"] == []

    async def test_list_files_filtered_by_language(
        self, client: AsyncClient, mock_workbench, override_dep
    ):
        """List files filtered by language."""
        f = _make_corpus_file(file_id=1, corpus_id=1, language="Python")
        mock_workbench.corpora.get_files = AsyncMock(return_value=[f])

        r = await client.get("/v1/corpora/1/files?language=Python")

        assert r.status_code == 200
        files = r.json()["data"]
        assert len(files) == 1
        mock_workbench.corpora.get_files.assert_called_with(1, "Python")

    async def test_get_corpus_file(
        self, client: AsyncClient, mock_workbench, override_dep
    ):
        """Get a specific file from a corpus."""
        f = _make_corpus_file(file_id=5, corpus_id=1)
        mock_workbench.corpora.get_file = AsyncMock(return_value=f)

        r = await client.get("/v1/corpora/1/files/5")

        assert r.status_code == 200
        data = r.json()["data"]
        assert data["id"] == 5
        assert data["corpus_id"] == 1
        assert data["encoding"] == "utf-8"
        assert r.json()["error"] is None

    async def test_get_corpus_file_not_found(
        self, client: AsyncClient, mock_workbench, override_dep
    ):
        """Get a non-existent file returns 404."""
        mock_workbench.corpora.get_file = AsyncMock(return_value=None)

        r = await client.get("/v1/corpora/1/files/99999")

        assert r.status_code == 404

    async def test_get_corpus_file_wrong_corpus(
        self, client: AsyncClient, mock_workbench, override_dep
    ):
        """Get a file that belongs to a different corpus returns 404."""
        f = _make_corpus_file(file_id=5, corpus_id=2)
        mock_workbench.corpora.get_file = AsyncMock(return_value=f)

        r = await client.get("/v1/corpora/1/files/5")

        assert r.status_code == 404


# ── Resolve Path ───────────────────────────────────────────────────────────


class TestResolvePath:
    """Tests for POST /v1/corpora/resolve-path."""

    async def test_resolve_path_empty(
        self, client: AsyncClient, mock_workbench, override_dep
    ):
        """Resolve with empty folder name returns 422."""
        r = await client.post(
            "/v1/corpora/resolve-path",
            json={"folder_name": ""},
        )
        assert r.status_code == 422

    async def test_resolve_path_not_found(
        self, client: AsyncClient, mock_workbench, override_dep
    ):
        """Resolve a non-existent folder returns null path."""
        r = await client.post(
            "/v1/corpora/resolve-path",
            json={"folder_name": "__nonexistent_folder_xyz__"},
        )
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["path"] is None
        assert data["root"] is None

    async def test_resolve_path_found(
        self, client: AsyncClient, mock_workbench, override_dep, tmp_path
    ):
        """Resolve a folder that exists in a workspace root."""
        project_dir = tmp_path / "ProjectX"
        project_dir.mkdir()

        with patch("anvil.api.v1.corpora.WORKSPACE_ROOTS", [str(tmp_path)]):
            r = await client.post(
                "/v1/corpora/resolve-path",
                json={"folder_name": "ProjectX"},
            )

        assert r.status_code == 200
        data = r.json()["data"]
        assert data["path"] is not None
        assert data["root"] == str(tmp_path)


# ── Analyze Path ──────────────────────────────────────────────────────────


class TestAnalyzePath:
    """Tests for POST /v1/corpora/analyze-path."""

    async def test_analyze_path(
        self, client: AsyncClient, mock_workbench, override_dep
    ):
        """Analyze a directory path with mocked scan result."""
        scan_result = CorpusScanResult(
            file_count=2,
            total_bytes=600,
            sizes=[200, 400],
            language_map={"Python": 2},
            language_sizes={"Python": [200, 400]},
        )

        with patch(
            "anvil.api.v1.corpora.CorpusLoader.scan",
            return_value=scan_result,
        ):
            r = await client.post(
                "/v1/corpora/analyze-path",
                json={"path": "/tmp/test"},
            )

        assert r.status_code == 200
        data = r.json()["data"]
        assert data["file_count"] == 2
        assert data["total_bytes"] == 600
        assert data["avg_bytes"] == 300
        assert data["median_bytes"] == 400
        assert data["language_breakdown"] == {"Python": 2}
        assert "recommendations" in data
        assert "language_stats" in data

    async def test_analyze_path_with_patterns(
        self, client: AsyncClient, mock_workbench, override_dep
    ):
        """Analyze with include/exclude patterns."""
        scan_result = CorpusScanResult(
            file_count=1,
            total_bytes=100,
            sizes=[100],
            language_map={"Python": 1},
            language_sizes={"Python": [100]},
        )

        with patch(
            "anvil.api.v1.corpora.CorpusLoader.scan",
            return_value=scan_result,
        ):
            r = await client.post(
                "/v1/corpora/analyze-path",
                json={
                    "path": "/tmp/test",
                    "include_patterns": ["*.py"],
                    "exclude_patterns": ["*.log"],
                },
            )

        assert r.status_code == 200
        assert r.json()["data"]["file_count"] == 1

    async def test_analyze_path_not_found(
        self, client: AsyncClient, mock_workbench, override_dep
    ):
        """Analyze a non-existent path returns 422."""
        with patch(
            "anvil.api.v1.corpora.CorpusLoader.scan",
            side_effect=NotADirectoryError("No such directory"),
        ):
            r = await client.post(
                "/v1/corpora/analyze-path",
                json={"path": "/nonexistent"},
            )

        assert r.status_code == 422

    async def test_analyze_path_empty_file_count(
        self, client: AsyncClient, mock_workbench, override_dep
    ):
        """Analyze a directory with no matching files."""
        scan_result = CorpusScanResult(
            file_count=0,
            total_bytes=0,
            sizes=[],
            language_map={},
            language_sizes={},
        )

        with patch(
            "anvil.api.v1.corpora.CorpusLoader.scan",
            return_value=scan_result,
        ):
            r = await client.post(
                "/v1/corpora/analyze-path",
                json={"path": "/tmp/empty"},
            )

        assert r.status_code == 200
        data = r.json()["data"]
        assert data["file_count"] == 0
        assert data["total_bytes"] == 0
        assert data["avg_bytes"] == 0
        assert data["median_bytes"] == 0
