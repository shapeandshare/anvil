"""E2E test: ingest corpus, start training with corpus_id, verify training starts."""

import tempfile
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_training_with_corpus(client):
    td = tempfile.mkdtemp()
    try:
        (Path(td) / "data.txt").write_text("hello\nworld\ntest\nfoo\nbar\n")

        r = await client.post(
            "/v1/corpora",
            json={
                "name": "train-e2e",
                "root_path": td,
                "chunking_strategy": "line",
            },
        )
        assert r.status_code == 200
        cid = r.json()["data"]["id"]

        r = await client.post(f"/v1/corpora/{cid}/ingest")
        assert r.status_code == 200

        r = await client.post(
            "/v1/training/start",
            json={
                "num_steps": 5,
                "n_embd": 8,
                "n_head": 2,
                "corpus_id": cid,
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "started"
        assert data["run_id"] is not None
    finally:
        import shutil
        shutil.rmtree(td)