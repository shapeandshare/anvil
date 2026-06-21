# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Shared test fixtures and helpers for the whole-API e2e test suite.

Provides factory fixtures for creating corpora, datasets, trained runs,
registered models, and eval datasets. Also provides utility helpers
for polling training run status and reading SSE streams.
"""

from __future__ import annotations

import asyncio
import json
import math
import tempfile
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient

TINY_TRAINING_CONFIG: dict[str, Any] = {
    "n_layer": 1,
    "n_embd": 16,
    "n_head": 4,
    "block_size": 16,
    "num_steps": 5,
    "learning_rate": 0.01,
    "beta1": 0.85,
    "beta2": 0.99,
    "temperature": 0.5,
    "compute_backend": "local-stdlib",
}
"""Smallest viable training configuration for e2e tests.

Valid because:
- head_dim = 16 // 4 = 4 (even) -- RoPE requirement
- n_head <= n_embd
- n_embd % n_head == 0
"""

CORPUS_SEED_TEXT = "Hello world. This is a tiny test corpus for anvil.\nIt has two sentences and some words.\n"
"""Deterministic ~100-byte corpus payload used for upload tests."""


def tiny_corpus_bytes() -> bytes:
    """Return a deterministic tiny corpus payload.

    Returns
    -------
    bytes
        UTF-8 encoded seed text.
    """
    return CORPUS_SEED_TEXT.encode("utf-8")


async def make_corpus(
    client: AsyncClient, tmp_path: Path | None = None
) -> dict[str, Any]:
    """Create and ingest a tiny corpus.

    Parameters
    ----------
    client : AsyncClient
        The test HTTP client.
    tmp_path : Path or None, optional
        Temporary directory for the corpus file. If ``None``, uses
        ``tempfile.mkdtemp()`` internally.

    Returns
    -------
    dict
        Corpus record with at least ``id`` and ``name`` keys.
    """
    td = tmp_path if tmp_path is not None else Path(tempfile.mkdtemp())
    corpus_file = td / "data.txt"
    corpus_file.write_text(CORPUS_SEED_TEXT)

    r = await client.post(
        "/v1/corpora",
        json={
            "name": "e2e-test-corpus",
            "root_path": str(td),
            "chunking_strategy": "line",
        },
    )
    assert (
        r.status_code == 200
    ), f"POST /v1/corpora: expected 200, got {r.status_code}: {r.text}"
    cid = r.json()["data"]["id"]

    r = await client.post(f"/v1/corpora/{cid}/ingest")
    assert (
        r.status_code == 200
    ), f"POST /v1/corpora/{cid}/ingest: expected 200, got {r.status_code}: {r.text}"
    return r.json()["data"]


async def make_dataset(
    client: AsyncClient,
    corpus_id: int | str | None = None,
) -> dict[str, Any]:
    """Create a ready-to-use dataset, optionally from a corpus.

    Parameters
    ----------
    client : AsyncClient
        The test HTTP client.
    corpus_id : int or None, optional
        If provided, creates the dataset from the given corpus via
        ``POST /v1/datasets/from-corpus``.

    Returns
    -------
    dict
        Dataset record with at least ``id`` and ``name`` keys.
    """
    if corpus_id is not None:
        r = await client.post(
            "/v1/datasets/from-corpus",
            json={"corpus_id": corpus_id, "name": "e2e-test-dataset"},
        )
    else:
        r = await client.post(
            "/v1/datasets",
            json={"name": "e2e-test-dataset"},
        )
    assert (
        r.status_code == 200
    ), f"POST /v1/datasets: expected 200, got {r.status_code}: {r.text}"
    return r.json()["data"]


async def poll_until_terminal(
    client: AsyncClient,
    run_id: str,
    timeout_s: int = 60,
) -> str:
    """Poll training run status until terminal or timeout.

    Parameters
    ----------
    client : AsyncClient
        The test HTTP client.
    run_id : str
        Training run UUID.
    timeout_s : int, optional
        Maximum seconds to wait (default ``60``).

    Returns
    -------
    str
        Terminal status: ``"completed"`` or ``"failed"``.

    Raises
    ------
    asyncio.TimeoutError
        If the run has not reached a terminal state within the timeout.
    """
    deadline = asyncio.get_event_loop().time() + timeout_s
    terminal_states = {"completed", "failed"}
    while asyncio.get_event_loop().time() < deadline:
        r = await client.get(f"/v1/training/{run_id}/status")
        assert (
            r.status_code == 200
        ), f"GET /v1/training/{run_id}/status: expected 200, got {r.status_code}"
        data = r.json().get("data", {})
        status = data.get("status", "")
        if status in terminal_states:
            return status
        await asyncio.sleep(1)
    msg = f"Training run {run_id} did not reach terminal state within {timeout_s}s"
    raise TimeoutError(msg)


async def read_sse_events(
    client: AsyncClient,
    url: str,
    max_events: int = 5,
    timeout_s: int = 30,
) -> list[tuple[str, dict[str, Any]]]:
    """Read SSE events from a streaming endpoint.

    Parameters
    ----------
    client : AsyncClient
        The test HTTP client.
    url : str
        SSE endpoint path (e.g., ``/v1/training/stream/{run_id}``).
    max_events : int, optional
        Stop after this many events (default ``5``).
    timeout_s : int, optional
        Maximum seconds to wait for ``max_events`` (default ``30``).

    Returns
    -------
    list of (str, dict)
        Each element is ``(event_name, payload_dict)``.

    Raises
    ------
    asyncio.TimeoutError
        If ``max_events`` are not received within the timeout.
    """
    deadline = asyncio.get_event_loop().time() + timeout_s
    events: list[tuple[str, dict[str, Any]]] = []
    current_event: str | None = None

    async with client.stream("GET", url) as response:
        assert (
            response.status_code == 200
        ), f"GET {url}: expected 200, got {response.status_code}"
        async for line in response.aiter_lines():
            if asyncio.get_event_loop().time() >= deadline:
                raise TimeoutError(
                    f"SSE {url}: expected {max_events} events within {timeout_s}s, "
                    f"got {len(events)}"
                )
            if line.startswith("event: "):
                current_event = line[7:]
            elif line.startswith("data: ") and current_event is not None:
                events.append((current_event, json.loads(line[6:])))
                if len(events) >= max_events:
                    break

    return events


async def make_trained_run(client: AsyncClient) -> dict[str, Any]:
    """Run a full tiny training run to terminal completion.

    Creates a corpus + dataset (self-seeding), starts training with
    the tiny config, and polls to terminal.

    Parameters
    ----------
    client : AsyncClient
        The test HTTP client.

    Returns
    -------
    dict
        Run metadata with keys ``run_id``, ``experiment_id``, ``status``,
        ``final_loss``.
    """
    import tempfile
    from pathlib import Path

    td = Path(tempfile.mkdtemp())
    try:
        corpus = await make_corpus(client, td)
        dataset = await make_dataset(client, corpus["id"])

        r = await client.post(
            "/v1/training/start",
            json={**TINY_TRAINING_CONFIG, "dataset_id": dataset["id"]},
        )
        assert (
            r.status_code == 200
        ), f"POST /v1/training/start: expected 200, got {r.status_code}: {r.text}"
        start_data = r.json()["data"]
        run_id = start_data["run_id"]
        experiment_id = start_data.get("experiment_id")

        status = await poll_until_terminal(client, run_id)

        r = await client.get(f"/v1/training/{run_id}/status")
        detail = r.json().get("data", {})
        final_loss = detail.get("final_loss", None)
        if final_loss is not None:
            assert math.isfinite(final_loss), f"Expected finite loss, got {final_loss}"

        return {
            "run_id": run_id,
            "experiment_id": experiment_id,
            "status": status,
            "final_loss": final_loss,
        }
    finally:
        import shutil

        shutil.rmtree(td, ignore_errors=True)


async def make_registered_model(client: AsyncClient) -> dict[str, Any]:
    """Train and register a model.

    Calls ``make_trained_run`` then registers via ``POST /v1/registry/models``.

    Parameters
    ----------
    client : AsyncClient
        The test HTTP client.

    Returns
    -------
    dict
        Registration metadata with keys ``model_id`` and ``version``.
    """
    run = await make_trained_run(client)

    r = await client.post(
        "/v1/registry/models",
        json={"run_id": run["run_id"]},
    )
    assert (
        r.status_code == 201
    ), f"POST /v1/registry/models: expected 201, got {r.status_code}: {r.text}"
    data = r.json()["data"]["model"]
    return {
        "model_id": data["id"],
        "version": data.get("version", 1),
    }


async def make_eval_dataset(client: AsyncClient) -> dict[str, Any]:
    """Create an eval dataset with a single record.

    Parameters
    ----------
    client : AsyncClient
        The test HTTP client.

    Returns
    -------
    dict
        Eval dataset metadata with key ``name``.
    """
    r = await client.post("/v1/eval-datasets", json={"name": "e2e-test-eval"})
    assert (
        r.status_code == 200
    ), f"POST /v1/eval-datasets: expected 200, got {r.status_code}: {r.text}"
    name = r.json()["data"]["name"]
    r = await client.post(
        f"/v1/eval-datasets/{name}/records",
        json={"records": [{"text": "test input"}]},
    )
    assert (
        r.status_code == 200
    ), f"POST /v1/eval-datasets/{name}/records: expected 200, got {r.status_code}: {r.text}"
    return {"name": name}
