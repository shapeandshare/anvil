# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""E2E tests for the corpora router."""

import tempfile
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_create_corpus(client):
    """Create a corpus via POST /v1/corpora."""
    td = tempfile.mkdtemp()
    try:
        (Path(td) / "data.txt").write_text("hello\nworld\ntest\n")

        r = await client.post(
            "/v1/corpora",
            json={
                "name": "create-e2e",
                "root_path": td,
                "chunking_strategy": "line",
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["error"] is None
        assert body["data"]["id"] is not None
        assert body["data"]["name"] == "create-e2e"
    finally:
        import shutil

        shutil.rmtree(td)


@pytest.mark.asyncio
async def test_ingest_corpus(client):
    """Create a corpus then POST /v1/corpora/{id}/ingest."""
    td = tempfile.mkdtemp()
    try:
        (Path(td) / "data.txt").write_text("hello\nworld\test\n")

        r = await client.post(
            "/v1/corpora",
            json={
                "name": "ingest-e2e",
                "root_path": td,
                "chunking_strategy": "line",
            },
        )
        assert r.status_code == 200
        cid = r.json()["data"]["id"]

        r = await client.post(f"/v1/corpora/{cid}/ingest")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["corpus_id"] == cid
        assert data["file_count"] >= 1
        assert data["document_count"] >= 1
    finally:
        import shutil

        shutil.rmtree(td)


@pytest.mark.asyncio
async def test_list_corpora(client):
    """GET /v1/corpora returns list of corpora."""
    td = tempfile.mkdtemp()
    try:
        (Path(td) / "data.txt").write_text("hello\nworld\n")

        await client.post(
            "/v1/corpora",
            json={
                "name": "list-e2e",
                "root_path": td,
                "chunking_strategy": "line",
            },
        )

        r = await client.get("/v1/corpora")
        assert r.status_code == 200
        body = r.json()
        assert body["error"] is None
        assert isinstance(body["data"], list)
        names = [c["name"] for c in body["data"]]
        assert "list-e2e" in names
    finally:
        import shutil

        shutil.rmtree(td)


@pytest.mark.asyncio
async def test_get_corpus_detail(client):
    """Create + ingest then GET /v1/corpora/{id} returns detail."""
    td = tempfile.mkdtemp()
    try:
        (Path(td) / "data.txt").write_text("hello\nworld\ntest\n")

        r = await client.post(
            "/v1/corpora",
            json={
                "name": "detail-e2e",
                "root_path": td,
                "chunking_strategy": "line",
            },
        )
        assert r.status_code == 200
        cid = r.json()["data"]["id"]

        await client.post(f"/v1/corpora/{cid}/ingest")

        r = await client.get(f"/v1/corpora/{cid}")
        assert r.status_code == 200
        body = r.json()
        assert body["error"] is None
        assert body["data"]["id"] == cid
        assert body["data"]["name"] == "detail-e2e"
    finally:
        import shutil

        shutil.rmtree(td)


@pytest.mark.asyncio
async def test_get_files(client):
    """Create + ingest then GET /v1/corpora/{id}/files returns file list."""
    td = tempfile.mkdtemp()
    try:
        (Path(td) / "data.txt").write_text("hello\nworld\ntest\n")

        r = await client.post(
            "/v1/corpora",
            json={
                "name": "files-e2e",
                "root_path": td,
                "chunking_strategy": "line",
            },
        )
        assert r.status_code == 200
        cid = r.json()["data"]["id"]

        await client.post(f"/v1/corpora/{cid}/ingest")

        r = await client.get(f"/v1/corpora/{cid}/files")
        assert r.status_code == 200
        body = r.json()
        assert body["error"] is None
        assert isinstance(body["data"], list)
        assert len(body["data"]) >= 1
    finally:
        import shutil

        shutil.rmtree(td)


@pytest.mark.asyncio
async def test_get_single_file(client):
    """Create + ingest then GET /v1/corpora/{id}/files/{fid} returns file."""
    td = tempfile.mkdtemp()
    try:
        (Path(td) / "data.txt").write_text("hello\nworld\ntest\n")

        r = await client.post(
            "/v1/corpora",
            json={
                "name": "singlefile-e2e",
                "root_path": td,
                "chunking_strategy": "line",
            },
        )
        assert r.status_code == 200
        cid = r.json()["data"]["id"]

        await client.post(f"/v1/corpora/{cid}/ingest")

        r = await client.get(f"/v1/corpora/{cid}/files")
        assert r.status_code == 200
        files = r.json()["data"]
        assert len(files) >= 1
        fid = files[0]["id"]

        r = await client.get(f"/v1/corpora/{cid}/files/{fid}")
        assert r.status_code == 200
        body = r.json()
        assert body["error"] is None
        assert body["data"]["id"] == fid
        assert body["data"]["corpus_id"] == cid
    finally:
        import shutil

        shutil.rmtree(td)


@pytest.mark.asyncio
async def test_fork_corpus(client):
    """Create + ingest then POST /v1/corpora/{id}/fork creates a new corpus."""
    td = tempfile.mkdtemp()
    try:
        (Path(td) / "data.txt").write_text("hello\nworld\ntest\n")

        r = await client.post(
            "/v1/corpora",
            json={
                "name": "fork-source",
                "root_path": td,
                "chunking_strategy": "line",
            },
        )
        assert r.status_code == 200
        cid = r.json()["data"]["id"]

        await client.post(f"/v1/corpora/{cid}/ingest")

        r = await client.post(
            f"/v1/corpora/{cid}/fork",
            json={"name": "forked-corpus"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["error"] is None
        assert body["data"]["id"] is not None
        assert body["data"]["name"] == "forked-corpus"
        assert body["data"]["id"] != cid
    finally:
        import shutil

        shutil.rmtree(td)


@pytest.mark.asyncio
async def test_delete_corpus(client):
    """Create then DELETE /v1/corpora/{id} removes the corpus."""
    td = tempfile.mkdtemp()
    try:
        (Path(td) / "data.txt").write_text("hello\nworld\n")

        r = await client.post(
            "/v1/corpora",
            json={
                "name": "delete-e2e",
                "root_path": td,
                "chunking_strategy": "line",
            },
        )
        assert r.status_code == 200
        cid = r.json()["data"]["id"]

        r = await client.delete(f"/v1/corpora/{cid}")
        assert r.status_code == 200
        body = r.json()
        assert body["error"] is None
        assert body["data"]["status"] == "deleted"

        r = await client.get(f"/v1/corpora/{cid}")
        assert r.status_code == 404
    finally:
        import shutil

        shutil.rmtree(td)


@pytest.mark.asyncio
async def test_corpus_404(client):
    """GET and DELETE on nonexistent corpus ID return 404."""
    r = await client.get("/v1/corpora/99999")
    assert r.status_code == 404

    r = await client.delete("/v1/corpora/99999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_resolve_path(client):
    """POST /v1/corpora/resolve-path returns 200 with a valid folder_name."""
    r = await client.post(
        "/v1/corpora/resolve-path",
        json={"folder_name": "anvil"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["error"] is None
    assert "path" in body["data"]
    assert "root" in body["data"]


@pytest.mark.asyncio
async def test_analyze_path(client):
    """POST /v1/corpora/analyze-path returns 200 with a valid path."""
    td = tempfile.mkdtemp()
    try:
        (Path(td) / "hello.py").write_text("print('hello')\n")
        (Path(td) / "readme.md").write_text("# Test\nDocs.\n")

        r = await client.post(
            "/v1/corpora/analyze-path",
            json={"path": td},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["error"] is None
        assert body["data"]["file_count"] == 2
        assert body["data"]["total_bytes"] > 0
        assert "Python" in body["data"]["language_breakdown"]
        assert len(body["data"]["recommendations"]) >= 1
    finally:
        import shutil

        shutil.rmtree(td)