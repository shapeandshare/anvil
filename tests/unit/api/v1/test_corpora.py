# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Comprehensive tests for the corpus management API endpoints.

Covers create, list, get, delete, fork, ingest, file listing,
resolve-path, analyze-path, and various error paths.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


# ── Corpora CRUD ─────────────────────────────────────────────────────────


class TestCorporaCRUD:
    """Tests for corpus CRUD endpoints."""

    async def test_create_corpus(self, client: AsyncClient, tmp_path):
        """Create a corpus from a directory path."""
        (tmp_path / "test.txt").write_text("hello world\n")
        r = await client.post(
            "/v1/corpora",
            json={"name": "My Corpus", "root_path": str(tmp_path)},
        )
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["name"] == "My Corpus"
        assert data["id"] > 0
        assert data["chunking_strategy"] == "windowed"

    async def test_create_corpus_with_full_config(self, client: AsyncClient, tmp_path):
        """Create a corpus with explicit chunking config."""
        (tmp_path / "test.txt").write_text("data\n")
        r = await client.post(
            "/v1/corpora",
            json={
                "name": "Full Config",
                "root_path": str(tmp_path),
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

    async def test_create_corpus_empty_name(self, client: AsyncClient):
        """Creating a corpus with an empty name returns 422."""
        r = await client.post(
            "/v1/corpora",
            json={"name": "   ", "root_path": "/tmp"},
        )
        assert r.status_code == 422

    async def test_list_corpora(self, client: AsyncClient, tmp_path):
        """List all corpora."""
        p1 = tmp_path / "corp1"
        p1.mkdir()
        p2 = tmp_path / "corp2"
        p2.mkdir()
        await client.post("/v1/corpora", json={"name": "List-A", "root_path": str(p1)})
        await client.post("/v1/corpora", json={"name": "List-B", "root_path": str(p2)})
        r = await client.get("/v1/corpora")
        assert r.status_code == 200
        names = [c["name"] for c in r.json()["data"]]
        assert "List-A" in names
        assert "List-B" in names

    async def test_get_corpus(self, client: AsyncClient, tmp_path):
        """Get a single corpus by ID."""
        (tmp_path / "f.txt").write_text("data\n")
        created = await client.post(
            "/v1/corpora", json={"name": "Get-It", "root_path": str(tmp_path)}
        )
        cid = created.json()["data"]["id"]
        r = await client.get(f"/v1/corpora/{cid}")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["name"] == "Get-It"

    async def test_get_corpus_not_found(self, client: AsyncClient):
        """Getting a non-existent corpus returns 404."""
        r = await client.get("/v1/corpora/99999")
        assert r.status_code == 404

    async def test_delete_corpus(self, client: AsyncClient, tmp_path):
        """Delete a corpus."""
        (tmp_path / "f.txt").write_text("data\n")
        created = await client.post(
            "/v1/corpora", json={"name": "Del-It", "root_path": str(tmp_path)}
        )
        cid = created.json()["data"]["id"]
        r = await client.delete(f"/v1/corpora/{cid}")
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "deleted"
        # Verify gone
        r2 = await client.get(f"/v1/corpora/{cid}")
        assert r2.status_code == 404

    async def test_delete_corpus_not_found(self, client: AsyncClient):
        """Deleting a non-existent corpus returns 404."""
        r = await client.delete("/v1/corpora/99999")
        assert r.status_code == 404


# ── Fork ─────────────────────────────────────────────────────────────────


class TestCorporaFork:
    """Tests for corpus fork endpoint."""

    async def test_fork_corpus(self, client: AsyncClient, tmp_path):
        """Fork a corpus."""
        (tmp_path / "f.txt").write_text("data\n")
        src = await client.post(
            "/v1/corpora", json={"name": "Parent", "root_path": str(tmp_path)}
        )
        src_id = src.json()["data"]["id"]
        r = await client.post(
            f"/v1/corpora/{src_id}/fork",
            json={"name": "Forked Corpus"},
        )
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["name"] == "Forked Corpus"
        assert data["id"] != src_id

    async def test_fork_corpus_not_found(self, client: AsyncClient):
        """Fork a non-existent corpus returns 422."""
        r = await client.post(
            "/v1/corpora/99999/fork",
            json={"name": "Orphan"},
        )
        assert r.status_code == 422


# ── Ingest ───────────────────────────────────────────────────────────────


class TestCorporaIngest:
    """Tests for corpus ingestion endpoints."""

    async def test_ingest_corpus(self, client: AsyncClient, tmp_path):
        """Ingest files from a corpus."""
        (tmp_path / "main.py").write_text("print('hello')\n")
        created = await client.post(
            "/v1/corpora",
            json={"name": "Ingest-Me", "root_path": str(tmp_path)},
        )
        cid = created.json()["data"]["id"]
        r = await client.post(f"/v1/corpora/{cid}/ingest")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["file_count"] == 1
        assert data["document_count"] > 0

    async def test_ingest_corpus_not_found(self, client: AsyncClient):
        """Ingest a non-existent corpus returns 422."""
        r = await client.post("/v1/corpora/99999/ingest")
        assert r.status_code == 422

    async def test_list_corpus_files(self, client: AsyncClient, tmp_path):
        """List files in a corpus."""
        (tmp_path / "a.py").write_text("x=1\n")
        (tmp_path / "b.py").write_text("y=2\n")
        created = await client.post(
            "/v1/corpora",
            json={"name": "File-List", "root_path": str(tmp_path)},
        )
        cid = created.json()["data"]["id"]
        await client.post(f"/v1/corpora/{cid}/ingest")
        r = await client.get(f"/v1/corpora/{cid}/files")
        assert r.status_code == 200
        files = r.json()["data"]
        assert len(files) == 2

    async def test_list_corpus_files_empty(self, client: AsyncClient, tmp_path):
        """List files in a corpus with no files matched."""
        created = await client.post(
            "/v1/corpora",
            json={"name": "Empty-Files", "root_path": str(tmp_path)},
        )
        cid = created.json()["data"]["id"]
        await client.post(f"/v1/corpora/{cid}/ingest")
        r = await client.get(f"/v1/corpora/{cid}/files")
        assert r.status_code == 200
        assert r.json()["data"] == []

    async def test_get_corpus_file(self, client: AsyncClient, tmp_path):
        """Get a specific file from a corpus."""
        (tmp_path / "unique.py").write_text("z=3\n")
        created = await client.post(
            "/v1/corpora",
            json={"name": "Get-File", "root_path": str(tmp_path)},
        )
        cid = created.json()["data"]["id"]
        await client.post(f"/v1/corpora/{cid}/ingest")
        files_r = await client.get(f"/v1/corpora/{cid}/files")
        file_id = files_r.json()["data"][0]["id"]
        r = await client.get(f"/v1/corpora/{cid}/files/{file_id}")
        assert r.status_code == 200
        assert r.json()["data"]["id"] == file_id

    async def test_get_corpus_file_not_found(self, client: AsyncClient, tmp_path):
        """Get a non-existent file returns 404."""
        (tmp_path / "f.py").write_text("pass\n")
        created = await client.post(
            "/v1/corpora",
            json={"name": "No-File", "root_path": str(tmp_path)},
        )
        cid = created.json()["data"]["id"]
        r = await client.get(f"/v1/corpora/{cid}/files/99999")
        assert r.status_code == 404

    async def test_list_files_filtered_by_language(self, client: AsyncClient, tmp_path):
        """List files filtered by language."""
        (tmp_path / "s.py").write_text("x=1\n")
        (tmp_path / "d.md").write_text("# title\n")
        created = await client.post(
            "/v1/corpora",
            json={"name": "Lang-Filter", "root_path": str(tmp_path)},
        )
        cid = created.json()["data"]["id"]
        await client.post(f"/v1/corpora/{cid}/ingest")
        r = await client.get(f"/v1/corpora/{cid}/files?language=Python")
        assert r.status_code == 200
        files = r.json()["data"]
        assert len(files) >= 1
        assert all(f["language"] == "Python" for f in files)

    async def test_list_files_no_language_filter(self, client: AsyncClient, tmp_path):
        """List files without language filter returns all."""
        (tmp_path / "s.py").write_text("x=1\n")
        created = await client.post(
            "/v1/corpora",
            json={"name": "No-Lang", "root_path": str(tmp_path)},
        )
        cid = created.json()["data"]["id"]
        await client.post(f"/v1/corpora/{cid}/ingest")
        r = await client.get(f"/v1/corpora/{cid}/files")
        assert r.status_code == 200

    async def test_ingest_max_files_limit(self, client: AsyncClient, tmp_path):
        """Ingest with max_files parameter."""
        for i in range(3):
            (tmp_path / f"f{i}.py").write_text(f"print({i})\n")
        created = await client.post(
            "/v1/corpora",
            json={"name": "Max-Files", "root_path": str(tmp_path)},
        )
        cid = created.json()["data"]["id"]
        r = await client.post(f"/v1/corpora/{cid}/ingest?max_files=2")
        assert r.status_code == 200
        # Only 2 of 3 files should be ingested
        assert r.json()["data"]["file_count"] == 2


# ── Resolve & Analyze Path ───────────────────────────────────────────────


class TestCorporaPathOperations:
    """Tests for path resolution and analysis endpoints."""

    async def test_resolve_path_not_found(self, client: AsyncClient):
        """Resolve a non-existent folder returns null path."""
        r = await client.post(
            "/v1/corpora/resolve-path",
            json={"folder_name": "__nonexistent_folder_xyz__"},
        )
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["path"] is None
        assert data["root"] is None

    async def test_resolve_path_empty(self, client: AsyncClient):
        """Resolve with empty folder name returns 422."""
        r = await client.post(
            "/v1/corpora/resolve-path",
            json={"folder_name": ""},
        )
        assert r.status_code == 422

    async def test_analyze_path(self, client: AsyncClient, tmp_path):
        """Analyze a directory path."""
        (tmp_path / "a.py").write_text("def foo():\n    pass\n")
        (tmp_path / "b.py").write_text("def bar():\n    return 1\n")
        r = await client.post(
            "/v1/corpora/analyze-path",
            json={"path": str(tmp_path)},
        )
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["file_count"] >= 1
        assert data["total_bytes"] > 0
        assert "recommendations" in data
        assert "language_breakdown" in data

    async def test_analyze_path_with_patterns(self, client: AsyncClient, tmp_path):
        """Analyze a directory path with include/exclude patterns."""
        (tmp_path / "keep.py").write_text("x=1\n")
        (tmp_path / "skip.log").write_text("log\n")
        r = await client.post(
            "/v1/corpora/analyze-path",
            json={
                "path": str(tmp_path),
                "include_patterns": ["*.py"],
                "exclude_patterns": ["*.log"],
            },
        )
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["file_count"] >= 1

    async def test_analyze_path_not_found(self, client: AsyncClient):
        """Analyze a non-existent path returns 422."""
        r = await client.post(
            "/v1/corpora/analyze-path",
            json={"path": "/tmp/__nonexistent_dir_xyz__/"},
        )
        assert r.status_code == 422


# ── MLflow Tracking Errors (degraded tracking) ────────────────────────────


class TestCorporaTrackingDegradation:
    """Tests that corpus endpoints handle MLflow tracking degradation."""

    async def test_create_corpus_tracking_failure(self, client: AsyncClient, tmp_path):
        """Create corpus succeeds even when MLflow tracking is degraded."""
        (tmp_path / "f.txt").write_text("data\n")
        with patch(
            "anvil.api.v1.corpora.tracking_svc.start_run",
            new_callable=AsyncMock,
            return_value=None,
        ):
            r = await client.post(
                "/v1/corpora",
                json={"name": "Degraded", "root_path": str(tmp_path)},
            )
            assert r.status_code == 200
            assert r.json()["data"]["name"] == "Degraded"
