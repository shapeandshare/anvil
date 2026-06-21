# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Contract tests for the widened training SSE signal surface.

Validates the neutral per-step ``metrics`` payload (including ``grad_norm`` and
``tokens_per_sec``), the new ``divergence`` event with run-halt semantics, and
the ``milestone`` cadence marker (feature 015-theme-engine, US2). These drive
the ``TrainingService`` progress closure and event stream directly to avoid the
database fixtures unrelated to this contract.
"""

import json
from unittest.mock import patch

import pytest

from anvil.services.training.divergence_error import DivergenceError
from anvil.services.training.step_metrics import StepMetrics


class _SyncQueue:
    """Collecting queue double whose ``put`` coroutine runs synchronously."""

    def __init__(self) -> None:
        self.items: list[dict] = []

    async def put(self, item: dict) -> None:
        self.items.append(item)


def _make_callback(num_steps: int = 100):
    """Build a progress callback wired to a synchronous collecting queue.

    Patches ``run_coroutine_threadsafe`` to execute the queued coroutine
    immediately, mirroring the production worker-thread marshalling without a
    second event loop.
    """
    from anvil.services.training.training import TrainingService

    svc = TrainingService()
    run_id = svc.reserve_run()
    queue = _SyncQueue()

    def _run_now(coro, _loop):
        try:
            coro.send(None)
        except StopIteration:
            pass

    patcher = patch(
        "anvil.services.training.training.asyncio.run_coroutine_threadsafe",
        side_effect=_run_now,
    )
    patcher.start()
    cb = svc._build_progress_callback(
        run_id=run_id,
        queue=queue,
        loop=None,
        device="cpu",
        num_steps=num_steps,
        progress_callback_override=None,
    )
    return svc, cb, queue, patcher


def test_metrics_payload_includes_new_neutral_fields():
    m = StepMetrics(
        step=5,
        loss=2.0,
        device="cpu",
        elapsed_sec=1.0,
        steps_per_sec=10.0,
        eta_sec=9.0,
        grad_norm=0.7,
        tokens_per_sec=160.0,
    )
    payload = json.loads(m.model_dump_json())
    for key in (
        "step",
        "loss",
        "device",
        "elapsed_sec",
        "steps_per_sec",
        "eta_sec",
        "grad_norm",
        "tokens_per_sec",
    ):
        assert key in payload
    assert payload["grad_norm"] == 0.7
    assert payload["tokens_per_sec"] == 160.0


def test_metrics_back_compat_keys_present():
    m = StepMetrics(step=1, loss=3.0, device="mps", elapsed_sec=0.5)
    payload = json.loads(m.model_dump_json())
    for key in ("step", "loss", "device", "elapsed_sec", "steps_per_sec", "eta_sec"):
        assert key in payload


def test_divergence_event_emitted_and_halts_without_complete():
    _, cb, queue, patcher = _make_callback()
    try:
        cb(0, 2.5, tokens=16, grad_norm=0.5)
        with pytest.raises(DivergenceError):
            cb(1, float("nan"), tokens=16, grad_norm=0.5)
    finally:
        patcher.stop()

    names = [e["event"] for e in queue.items]
    assert "metrics" in names
    assert "divergence" in names
    assert "complete" not in names
    div = next(e for e in queue.items if e["event"] == "divergence")
    assert json.loads(div["data"])["reason"] == "loss_nan"


def test_milestone_marker_emitted_on_cadence():
    _, cb, queue, patcher = _make_callback(num_steps=100)
    try:
        for step in range(0, 11):
            cb(step, 2.0, tokens=8, grad_norm=0.1)
    finally:
        patcher.stop()

    milestones = [e for e in queue.items if e["event"] == "milestone"]
    assert milestones
    assert json.loads(milestones[0]["data"])["step"] == 10


def test_stdlib_style_none_grad_norm_is_serializable():
    _, cb, queue, patcher = _make_callback()
    try:
        cb(0, 2.0, tokens=8, grad_norm=None)
        cb(1, 1.9, tokens=8, grad_norm=None)
    finally:
        patcher.stop()

    metric = next(e for e in queue.items if e["event"] == "metrics")
    assert json.loads(metric["data"])["grad_norm"] is None


def test_diverged_run_status_is_tracked():
    from anvil.services.training.training import TrainingService

    svc = TrainingService()
    assert svc.is_diverged(123) is False
    svc._diverged_runs.add(123)
    assert svc.is_diverged(123) is True
