# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for corpus API endpoints."""

import pytest


@pytest.mark.asyncio
async def test_create_corpus(client):
    r = await client.post(
        "/v1/corpora",
        json={"name": "api-test", "root_path": "/tmp"},
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["name"] == "api-test"
    assert data["id"] > 0


@pytest.mark.asyncio
async def test_create_corpus_validation(client):
    r = await client.post(
        "/v1/corpora",
        json={"name": "valid-test", "root_path": "/tmp"},
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_list_corpora(client):
    await client.post(
        "/v1/corpora",
        json={"name": "list-a", "root_path": "/a"},
    )
    r = await client.get("/v1/corpora")
    assert r.status_code == 200
    names = [c["name"] for c in r.json()["data"]]
    assert "list-a" in names


@pytest.mark.asyncio
async def test_get_corpus(client):
    created = await client.post(
        "/v1/corpora",
        json={"name": "get-api", "root_path": "/tmp"},
    )
    cid = created.json()["data"]["id"]
    r = await client.get(f"/v1/corpora/{cid}")
    assert r.status_code == 200
    assert r.json()["data"]["name"] == "get-api"


@pytest.mark.asyncio
async def test_get_corpus_not_found(client):
    r = await client.get("/v1/corpora/9999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_corpus(client):
    created = await client.post(
        "/v1/corpora",
        json={"name": "del-api", "root_path": "/tmp"},
    )
    cid = created.json()["data"]["id"]
    r = await client.delete(f"/v1/corpora/{cid}")
    assert r.status_code == 200
    r2 = await client.get(f"/v1/corpora/{cid}")
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_ingest_corpus(client):
    import tempfile

    td = tempfile.mkdtemp()
    try:
        from pathlib import Path

        (Path(td) / "test.py").write_text("print('hello')\n")
        created = await client.post(
            "/v1/corpora",
            json={"name": "ingest-api", "root_path": td},
        )
        cid = created.json()["data"]["id"]
        r = await client.post(f"/v1/corpora/{cid}/ingest")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["file_count"] == 1
        assert data["document_count"] > 0
    finally:
        import shutil

        shutil.rmtree(td)


@pytest.mark.asyncio
async def test_list_corpus_files(client):
    import tempfile

    td = tempfile.mkdtemp()
    try:
        from pathlib import Path

        (Path(td) / "main.py").write_text("x=1\n")
        (Path(td) / "utils.py").write_text("y=2\n")
        created = await client.post(
            "/v1/corpora",
            json={"name": "files-api", "root_path": td},
        )
        cid = created.json()["data"]["id"]
        await client.post(f"/v1/corpora/{cid}/ingest")
        r = await client.get(f"/v1/corpora/{cid}/files")
        assert r.status_code == 200
        files = r.json()["data"]
        assert len(files) == 2
    finally:
        import shutil

        shutil.rmtree(td)


@pytest.mark.asyncio
async def test_list_corpus_files_empty(client):
    import tempfile

    td = tempfile.mkdtemp()
    try:
        created = await client.post(
            "/v1/corpora",
            json={"name": "empty-files", "root_path": td},
        )
        cid = created.json()["data"]["id"]
        await client.post(f"/v1/corpora/{cid}/ingest")
        r = await client.get(f"/v1/corpora/{cid}/files")
        assert r.status_code == 200
        assert r.json()["data"] == []
    finally:
        import shutil

        shutil.rmtree(td)
