"""E2E test for corpus lifecycle — create, ingest, verify stats, delete."""

import tempfile
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_corpus_lifecycle(client):
    td = tempfile.mkdtemp()
    try:
        (Path(td) / "main.py").write_text("def hello():\n    pass\n")
        (Path(td) / "utils.py").write_text("import os\nimport sys\n")
        (Path(td) / "README.md").write_text("# Project\nDocs.\n")

        r = await client.post(
            "/v1/corpora",
            json={
                "name": "lifecycle-test",
                "root_path": td,
                "chunking_strategy": "windowed",
                "chunk_overlap": 0.5,
            },
        )
        assert r.status_code == 200
        cid = r.json()["data"]["id"]

        r = await client.post(f"/v1/corpora/{cid}/ingest")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["file_count"] == 3
        assert data["document_count"] > 0
        assert "Python" in data["language_map"]
        assert "Markdown" in data["language_map"]

        r = await client.get(f"/v1/corpora/{cid}")
        assert r.status_code == 200
        c = r.json()["data"]
        assert c["file_count"] == 3

        r = await client.get(f"/v1/corpora/{cid}/files")
        assert r.status_code == 200
        files = r.json()["data"]
        assert len(files) == 3
        paths = {f["relative_path"] for f in files}
        assert "main.py" in paths
        assert "utils.py" in paths
        assert "README.md" in paths

        r = await client.delete(f"/v1/corpora/{cid}")
        assert r.status_code == 200

        r = await client.get(f"/v1/corpora/{cid}")
        assert r.status_code == 404
    finally:
        import shutil
        shutil.rmtree(td)