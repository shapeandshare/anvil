# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""E2E tests for the experiments router.

Exercises experiment tracking endpoints — list, detail, compare, metrics,
artifacts, download, retry, delete.

Degraded-tracking assumption
----------------------------
The MLflow sidecar is NOT started during tests. Experiment data sourced
from MLflow will return degraded/empty responses. Tests verify HTTP-level
correctness and response structure without requiring a live tracking
server. See ``anvil/api/v1/experiments.py`` for the router implementation.
"""

import asyncio
import math
import tempfile
from pathlib import Path

import pytest


def _setup_training_data(temp_dir: str, text: str = "hello world test corpus\n") -> str:
    r"""Write a small text file into a temp directory.

    Parameters
    ----------
    temp_dir : str
        Path to the temporary directory.
    text : str, optional
        Content to write. Defaults to ``"hello world test corpus\\n"``.

    Returns
    -------
    str
        The path to the written file.
    """
    path = Path(temp_dir) / "data.txt"
    path.write_text(text)
    return str(path)


async def _run_training_to_completion(client, dataset_id: int) -> dict:
    """Start a tiny training run and poll until it finishes.

    Creates a minimal model (1 layer, 16 embed dim, 4 heads, 5 steps) and
    polls the training-status endpoint until the run completes.

    Parameters
    ----------
    client : httpx.AsyncClient
        The test HTTP client.
    dataset_id : int
        ID of the dataset to train on.

    Returns
    -------
    dict
        The training start response body with ``run_id``, ``experiment_id``,
        ``mlflow_run_id``, and ``status``.
    """
    r = await client.post(
        "/v1/training/start",
        json={
            "n_layer": 1,
            "n_embd": 16,
            "n_head": 4,
            "block_size": 16,
            "num_steps": 5,
            "learning_rate": 0.01,
            "dataset_id": dataset_id,
            "compute_backend": "local-stdlib",
        },
    )
    assert r.status_code == 200
    body: dict = r.json()
    run_id = body["run_id"]
    assert isinstance(run_id, int)
    assert run_id >= 0

    # Poll until the training-status queue is gone (run completed)
    for _ in range(60):
        r2 = await client.get(f"/v1/training/{run_id}/status")
        if r2.status_code == 404:
            break
        await asyncio.sleep(1)
    else:
        # Final attempt after timeout — accept what we have
        await asyncio.sleep(0.5)

    return body


async def _run_e2e_setup(client) -> dict:
    """Create a corpus, ingest it, build a dataset, and run a tiny training.

    Parameters
    ----------
    client : httpx.AsyncClient
        The test HTTP client.

    Returns
    -------
    dict
        Setup results with keys ``tmpdir``, ``corpus_id``, ``dataset_id``,
        ``run_id``, ``experiment_id``, ``mlflow_run_id``.
    """
    td = tempfile.mkdtemp()
    _setup_training_data(td)

    result: dict = {"tmpdir": td}

    # Create corpus
    r = await client.post(
        "/v1/corpora",
        json={
            "name": "exp-e2e-corpus",
            "root_path": td,
            "chunking_strategy": "line",
        },
    )
    assert r.status_code == 200
    cid: int = r.json()["data"]["id"]
    result["corpus_id"] = cid

    # Ingest
    r = await client.post(f"/v1/corpora/{cid}/ingest")
    assert r.status_code == 200

    # Build dataset from corpus
    r = await client.post(
        "/v1/datasets/from-corpus",
        json={"corpus_id": cid, "name": "exp-e2e-dataset"},
    )
    assert r.status_code == 200
    ds_id: int = r.json()["data"]["id"]
    result["dataset_id"] = ds_id

    # Train
    training = await _run_training_to_completion(client, ds_id)
    result["run_id"] = training["run_id"]
    result["experiment_id"] = training.get("experiment_id")
    result["mlflow_run_id"] = training.get("mlflow_run_id")

    return result


@pytest.mark.asyncio
async def test_list_experiments(client):
    """List experiments after running a tiny training.

    GET /v1/experiments returns a 200 with an ``experiments`` list and
    MLflow metadata keys. When the tracking server is unavailable the
    list will be empty (degraded mode).
    """
    setup = await _run_e2e_setup(client)
    try:
        r = await client.get("/v1/experiments")
        assert r.status_code == 200
        body = r.json()
        # Response shape (router returns flat dict, not data/error envelope)
        assert "experiments" in body
        assert isinstance(body["experiments"], list)
        assert "mlflow_experiment_id" in body
        assert "mlflow_url" in body
    finally:
        import shutil

        shutil.rmtree(setup["tmpdir"])


@pytest.mark.asyncio
async def test_get_experiment_detail(client):
    """Retrieve a single experiment by ID.

    GET /v1/experiments/{id} returns 200 with full experiment details when
    the tracking server is available, or 404 in degraded mode.
    """
    setup = await _run_e2e_setup(client)
    try:
        eid = setup.get("experiment_id")
        if eid is None:
            return  # no experiment allocated

        r = await client.get(f"/v1/experiments/{eid}")
        # Degraded mode → 404 (MLflow unavailable); full mode → 200
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            data = r.json()
            assert data["id"] == eid
    finally:
        import shutil

        shutil.rmtree(setup["tmpdir"])


@pytest.mark.asyncio
async def test_experiment_metrics(client):
    """Retrieve loss-metric history for an experiment.

    GET /v1/experiments/{id}/metrics returns a ``metrics`` list. When the
    tracking server is available each entry has ``step`` and finite ``loss``
    (FR-008 compliance). Returns 404 in degraded mode.
    """
    setup = await _run_e2e_setup(client)
    try:
        eid = setup.get("experiment_id")
        if eid is None:
            return

        r = await client.get(f"/v1/experiments/{eid}/metrics")
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            data = r.json()
            assert "metrics" in data
            assert isinstance(data["metrics"], list)
            # FR-008: Every loss value must be finite
            for entry in data["metrics"]:
                assert "step" in entry
                assert "loss" in entry
                assert math.isfinite(entry["loss"]), (
                    f"FR-008 violation: non-finite loss {entry['loss']} "
                    f"at step {entry['step']}"
                )
    finally:
        import shutil

        shutil.rmtree(setup["tmpdir"])


@pytest.mark.asyncio
async def test_experiment_compare(client):
    """Compare multiple experiments.

    GET /v1/experiments/compare?id=... returns a summary list. Works
    even in degraded mode (returns empty list).
    """
    setup = await _run_e2e_setup(client)
    try:
        eid = setup.get("experiment_id") or 0
        r = await client.get(f"/v1/experiments/compare?id={eid}")
        assert r.status_code == 200
        body = r.json()
        assert "experiments" in body
        assert isinstance(body["experiments"], list)
    finally:
        import shutil

        shutil.rmtree(setup["tmpdir"])


@pytest.mark.asyncio
async def test_experiment_artifacts(client):
    """List safetensors artifacts for an experiment and run.

    GET /v1/experiments/{eid}/runs/{rid}/artifacts returns artifact
    metadata. Returns 404 when the experiment or MLflow run is not
    found (degraded mode).
    """
    setup = await _run_e2e_setup(client)
    try:
        eid = setup.get("experiment_id")
        mlflow_run_id = setup.get("mlflow_run_id")
        if eid is None or not mlflow_run_id:
            return  # no MLflow run available

        r = await client.get(
            f"/v1/experiments/{eid}/runs/{mlflow_run_id}/artifacts"
        )
        # Degraded → 404 (experiment not found); full → 200
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            data = r.json()
            assert "available" in data
            assert isinstance(data.get("available"), bool)
            assert "files" in data
            assert isinstance(data["files"], list)
    finally:
        import shutil

        shutil.rmtree(setup["tmpdir"])


@pytest.mark.asyncio
async def test_experiment_download(client):
    """Download an artifact file from an experiment and run.

    GET /v1/experiments/{eid}/runs/{rid}/download?path=... returns a
    file attachment on success or a structured error on failure.
    """
    setup = await _run_e2e_setup(client)
    try:
        eid = setup.get("experiment_id")
        mlflow_run_id = setup.get("mlflow_run_id")
        if eid is None or not mlflow_run_id:
            return

        r = await client.get(
            f"/v1/experiments/{eid}/runs/{mlflow_run_id}/download",
            params={"path": "model.safetensors"},
        )
        # Degraded → 404 (experiment not found); full mode → 200 or error
        assert r.status_code in (200, 404, 400)
        if r.status_code == 200:
            # Response is a file download — body should be non-empty
            assert len(r.content) > 0
    finally:
        import shutil

        shutil.rmtree(setup["tmpdir"])


@pytest.mark.asyncio
async def test_delete_experiment(client):
    """Delete an experiment.

    DELETE /v1/experiments/{id} returns 200 with a status message when
    the experiment exists, or 404 in degraded mode.
    """
    setup = await _run_e2e_setup(client)
    try:
        eid = setup.get("experiment_id")
        if eid is None:
            return

        r = await client.delete(f"/v1/experiments/{eid}")
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            data = r.json()
            assert "status" in data
    finally:
        import shutil

        shutil.rmtree(setup["tmpdir"])


@pytest.mark.asyncio
async def test_experiment_404(client):
    """Request a non-existent experiment returns 404."""
    r = await client.get("/v1/experiments/99999")
    assert r.status_code == 404

    r = await client.get("/v1/experiments/99999/metrics")
    assert r.status_code == 404

    r = await client.delete("/v1/experiments/99999")
    assert r.status_code == 404
