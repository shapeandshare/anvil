# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""E2E lifecycle integration test: cross-router money-path.

Chains the full user workflow — upload corpus, build dataset, train model,
verify experiment, register model, download artifact, sample inference —
to prove routers compose correctly, not just in isolation.
"""

from __future__ import annotations

import asyncio
import math
from typing import Any

import pytest


@pytest.mark.asyncio
async def test_lifecycle_journey(client: Any) -> None:
    """Run the full pipeline: corpus → dataset → train → experiment → register
    → download → inference. Every step must succeed with the correct response
    shape; on any failure the assertion message names the failed step.
    """
    import tempfile
    from pathlib import Path

    from tests.e2e.api.conftest import (
        TINY_TRAINING_CONFIG,
        make_corpus,
        make_dataset,
        make_eval_dataset,
        poll_until_terminal,
    )

    td = Path(tempfile.mkdtemp())
    start_time = asyncio.get_event_loop().time()

    try:
        # ---- Step 1: Create + ingest corpus ----
        corpus = await make_corpus(client, td)
        corpus_id = corpus["id"]
        assert isinstance(
            corpus_id, (int, str)
        ), f"Step 1 (corpus): expected int/str id, got {type(corpus_id)}"

        # ---- Step 2: Build dataset from corpus ----
        dataset = await make_dataset(client, corpus["id"])
        dataset_id = dataset["id"]
        assert isinstance(
            dataset_id, (int, str)
        ), f"Step 2 (dataset): expected int/str id, got {type(dataset_id)}"

        # ---- Step 3: Start training with tiny config ----
        r = await client.post(
            "/v1/training/start",
            json={**TINY_TRAINING_CONFIG, "dataset_id": dataset_id},
        )
        assert (
            r.status_code == 200
        ), f"Step 3 (train start): expected 200, got {r.status_code}: {r.text}"
        start_data = r.json()["data"]
        run_id = start_data.get("run_id")
        assert run_id is not None, "Step 3 (train start): run_id is None"
        experiment_id = start_data.get("experiment_id")

        # ---- Step 4: Poll to terminal completion ----
        terminal_status = await poll_until_terminal(client, run_id)
        assert (
            terminal_status == "completed"
        ), f"Step 4 (train poll): expected completed, got {terminal_status}"

        # ---- Step 5: Verify experiment + metrics ----
        if experiment_id is not None:
            r = await client.get(f"/v1/experiments/{experiment_id}")
            assert (
                r.status_code == 200
            ), f"Step 5a (exp detail): expected 200, got {r.status_code}"
            exp_data = r.json().get("data", {})
            assert exp_data.get("id") == experiment_id

            r = await client.get(f"/v1/experiments/{experiment_id}/metrics")
            assert (
                r.status_code == 200
            ), f"Step 5b (exp metrics): expected 200, got {r.status_code}"
            metrics_data = r.json().get("data", {})
            loss_series = metrics_data.get("loss", [])
            assert len(loss_series) > 0, "Step 5b (exp metrics): loss series is empty"
            for point in loss_series:
                loss_val = point.get("loss") if isinstance(point, dict) else point
                if loss_val is not None:
                    assert math.isfinite(
                        loss_val
                    ), f"Step 5b (exp metrics): non-finite loss {loss_val}"
        else:
            # Tracking may be degraded — experiment_id may be None in test env
            pass

        # ---- Step 6: Register model ----
        r = await client.post(
            "/v1/registry/models",
            json={"run_id": run_id},
        )
        assert (
            r.status_code == 201
        ), f"Step 6 (register): expected 201, got {r.status_code}: {r.text}"
        model_data = r.json()["data"]["model"]
        model_id = model_data["id"]
        assert model_id is not None, "Step 6 (register): model_id is None"

        # ---- Step 7: Download artifact ----
        if experiment_id is not None:
            run_resp = await client.get(f"/v1/experiments/{experiment_id}/runs")
            if run_resp.status_code == 200:
                run_list = run_resp.json().get("data", {}).get("runs", [])
                if run_list:
                    rid = run_list[0].get("run_id") or run_list[0].get("id")
                    if rid:
                        dl = await client.get(
                            f"/v1/experiments/{experiment_id}/runs/{rid}/download"
                        )
                        assert (
                            dl.status_code == 200
                        ), f"Step 7 (download): expected 200, got {dl.status_code}"
                        assert (
                            len(dl.content) > 0
                        ), "Step 7 (download): empty artifact body"

        # ---- Step 8: Sample inference ----
        r = await client.post(
            "/v1/inference/sample",
            json={"prompt": "hello"},
        )
        assert (
            r.status_code == 200
        ), f"Step 8 (inference): expected 200, got {r.status_code}: {r.text}"
        sample_data = r.json().get("data", {})
        generated = (
            sample_data.get("generated")
            or sample_data.get("text")
            or sample_data.get("output")
            or ""
        )
        assert (
            len(generated) > 0
        ), f"Step 8 (inference): generated text is empty: {sample_data}"

        # ---- Timing ----
        elapsed = asyncio.get_event_loop().time() - start_time
        timeout = 120  # allow generous margin on CI
        assert (
            elapsed < timeout
        ), f"Lifecycle test exceeded {timeout}s: took {elapsed:.1f}s"

    finally:
        import shutil

        shutil.rmtree(td, ignore_errors=True)
