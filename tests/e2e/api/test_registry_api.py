# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""E2E tests for the model registry router."""

import asyncio
import tempfile
from pathlib import Path

import pytest


async def _poll_until_complete(
    client,
    run_id: int,
    timeout_s: int = 60,
) -> None:
    """Poll training status until the run completes.

    The training status endpoint returns 200 while the run is active,
    and 404 once the run completes and its task is cleaned up.

    Parameters
    ----------
    client :
        The test HTTP client.
    run_id : int
        Training run ID returned from ``POST /v1/training/start``.
    timeout_s : int, optional
        Maximum seconds to wait (default ``60``).

    Raises
    ------
    asyncio.TimeoutError
        If the run does not complete within the timeout.
    """
    deadline = asyncio.get_event_loop().time() + timeout_s
    while asyncio.get_event_loop().time() < deadline:
        r = await client.get(f"/v1/training/{run_id}/status")
        if r.status_code == 404:
            return
        await asyncio.sleep(1)
    msg = f"Training run {run_id} did not complete within {timeout_s}s"
    raise TimeoutError(msg)


async def _train_and_register(client) -> dict:
    """Run a tiny training job and register the resulting model.

    Creates a temp directory with a single-line corpus, POSTs to
    create+ingest the corpus, creates a dataset from it, starts a
    5-step training run, polls until completion, then registers the
    model via the registry endpoint.

    Parameters
    ----------
    client :
        The test HTTP client.

    Returns
    -------
    dict
        Registration result from ``POST /v1/registry/models`` with
        keys ``name``, ``version``, ``run_id``, ``source``.
    """
    td = Path(tempfile.mkdtemp())
    try:
        (td / "data.txt").write_text("hello world test corpus\n")
        r = await client.post(
            "/v1/corpora",
            json={
                "name": "reg-e2e",
                "root_path": str(td),
                "chunking_strategy": "line",
            },
        )
        assert r.status_code == 200, (
            f"POST /v1/corpora: {r.status_code}: {r.text}"
        )
        cid = r.json()["data"]["id"]

        r = await client.post(f"/v1/corpora/{cid}/ingest")
        assert r.status_code == 200, (
            f"POST /v1/corpora/{cid}/ingest: {r.status_code}: {r.text}"
        )

        r = await client.post(
            "/v1/datasets/from-corpus",
            json={"corpus_id": cid, "name": "reg-ds"},
        )
        assert r.status_code == 200, (
            f"POST /v1/datasets/from-corpus: {r.status_code}: {r.text}"
        )
        ds_id = r.json()["data"]["id"]

        r = await client.post(
            "/v1/training/start",
            json={
                "n_layer": 1,
                "n_embd": 16,
                "n_head": 4,
                "block_size": 16,
                "num_steps": 5,
                "learning_rate": 0.01,
                "dataset_id": ds_id,
                "compute_backend": "local-stdlib",
            },
        )
        assert r.status_code == 200, (
            f"POST /v1/training/start: {r.status_code}: {r.text}"
        )
        start_data = r.json()
        run_id = start_data["run_id"]
        experiment_id = start_data["experiment_id"]

        await _poll_until_complete(client, run_id)
        await asyncio.sleep(0.5)

        r = await client.post(
            "/v1/registry/models",
            json={"experiment_id": experiment_id},
        )
        assert r.status_code == 201, (
            f"POST /v1/registry/models: {r.status_code}: {r.text}"
        )
        return r.json()
    finally:
        import shutil

        shutil.rmtree(td)


@pytest.mark.asyncio
async def test_register_model(client):
    """POST /v1/registry/models returns 201 with model name and version."""
    reg_data = await _train_and_register(client)
    assert isinstance(reg_data, dict)
    assert "name" in reg_data
    assert isinstance(reg_data["name"], str)
    assert "version" in reg_data


@pytest.mark.asyncio
async def test_list_models(client):
    """GET /v1/registry/models returns the registered model in the list."""
    reg_data = await _train_and_register(client)
    model_name = reg_data["name"]

    r = await client.get("/v1/registry/models")
    assert r.status_code == 200, (
        f"GET /v1/registry/models: {r.status_code}: {r.text}"
    )
    data = r.json()
    assert isinstance(data, dict)
    models = data.get("models", [])
    assert isinstance(models, list)
    assert len(models) >= 1

    names = [m["name"] for m in models]
    assert model_name in names, (
        f"Expected model '{model_name}' in list, got {names}"
    )


@pytest.mark.asyncio
async def test_get_model_detail(client):
    """GET /v1/registry/models/{name} returns full model details."""
    reg_data = await _train_and_register(client)
    model_name = reg_data["name"]

    r = await client.get(f"/v1/registry/models/{model_name}")
    assert r.status_code == 200, (
        f"GET /v1/registry/models/{model_name}: {r.status_code}: {r.text}"
    )
    detail = r.json()
    assert isinstance(detail, dict)
    assert detail.get("name") == model_name
    assert "versions" in detail
    assert isinstance(detail["versions"], list)
    assert len(detail["versions"]) >= 1


@pytest.mark.asyncio
async def test_get_model_version(client):
    """GET /v1/registry/models/{name}/versions/{v} returns version details."""
    reg_data = await _train_and_register(client)
    model_name = reg_data["name"]
    version = reg_data["version"]

    r = await client.get(
        f"/v1/registry/models/{model_name}/versions/{version}",
    )
    assert r.status_code == 200, (
        f"GET /v1/registry/models/{model_name}/versions/{version}: "
        f"{r.status_code}: {r.text}"
    )
    detail = r.json()
    assert isinstance(detail, dict)
    assert str(detail.get("version")) == str(version)


@pytest.mark.asyncio
async def test_delete_model_version(client):
    """DELETE /v1/registry/models/{name}/versions/{v} returns 200."""
    reg_data = await _train_and_register(client)
    model_name = reg_data["name"]
    version = reg_data["version"]

    r = await client.delete(
        f"/v1/registry/models/{model_name}/versions/{version}",
    )
    assert r.status_code == 200, (
        f"DELETE /v1/registry/models/{model_name}/versions/{version}: "
        f"{r.status_code}: {r.text}"
    )
    result = r.json()
    assert isinstance(result, dict)
    assert "message" in result


@pytest.mark.asyncio
async def test_delete_model(client):
    """DELETE /v1/registry/models/{name} returns 200 and removes the model."""
    reg_data = await _train_and_register(client)
    model_name = reg_data["name"]

    r = await client.delete(f"/v1/registry/models/{model_name}")
    assert r.status_code == 200, (
        f"DELETE /v1/registry/models/{model_name}: {r.status_code}: {r.text}"
    )
    result = r.json()
    assert isinstance(result, dict)
    assert "message" in result

    r = await client.get(f"/v1/registry/models/{model_name}")
    assert r.status_code == 404, (
        f"GET /v1/registry/models/{model_name} after delete: "
        f"expected 404, got {r.status_code}"
    )


@pytest.mark.asyncio
async def test_registry_404(client):
    """Verify 404 for nonexistent model and 400 for bad experiment_id."""
    r = await client.get("/v1/registry/models/nonexistent-model-name")
    assert r.status_code == 404, (
        f"Expected 404 for nonexistent model, got {r.status_code}: {r.text}"
    )

    r = await client.get("/v1/registry/models/99999")
    assert r.status_code == 404, (
        f"Expected 404 for nonexistent model ID, got {r.status_code}: {r.text}"
    )

    r = await client.post(
        "/v1/registry/models",
        json={"experiment_id": 99999},
    )
    assert r.status_code == 400, (
        f"Expected 400 for bad experiment_id, got {r.status_code}: {r.text}"
    )

    r = await client.post("/v1/registry/models", json={})
    assert r.status_code == 400, (
        f"Expected 400 for missing experiment_id, got {r.status_code}: {r.text}"
    )
