# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for training route validation.

Tests ``_validate_hparams`` directly and exercises the SSE stream
gone-case and forward-pass-graph 404 via mocked module-level
singletons.
"""

from __future__ import annotations

import json
from unittest.mock import ANY, AsyncMock

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from anvil.api.app import app
from anvil.api.deps import get_api_key_store


######################################################################
# _validate_hparams
######################################################################


class TestValidateHparams:
    """Direct tests for ``_validate_hparams`` sanity constraints."""

    @staticmethod
    def test_n_head_exceeds_n_embd_raises_422() -> None:
        """n_head (8) > n_embd (4) must raise HTTP 422."""
        from anvil.api.v1.training import _validate_hparams

        with pytest.raises(HTTPException) as exc_info:
            _validate_hparams(n_embd=4, n_head=8, _block_size=16)
        assert exc_info.value.status_code == 422
        assert "n_head" in exc_info.value.detail
        assert "n_embd" in exc_info.value.detail

    @staticmethod
    def test_not_divisible_raises_422() -> None:
        """n_embd=16, n_head=3 (not divisible) must raise HTTP 422."""
        from anvil.api.v1.training import _validate_hparams

        with pytest.raises(HTTPException) as exc_info:
            _validate_hparams(n_embd=16, n_head=3, _block_size=16)
        assert exc_info.value.status_code == 422
        assert "not divisible" in exc_info.value.detail

    @staticmethod
    def test_odd_head_dim_raises_422() -> None:
        """head_dim=3 (12/4) is odd — RoPE requires even, must raise 422."""
        from anvil.api.v1.training import _validate_hparams

        with pytest.raises(HTTPException) as exc_info:
            _validate_hparams(n_embd=12, n_head=4, _block_size=16)
        assert exc_info.value.status_code == 422
        assert "odd" in exc_info.value.detail
        assert "RoPE" in exc_info.value.detail

    @staticmethod
    def test_valid_hparams_passes() -> None:
        """16 embd, 4 heads, even head_dim — must not raise."""
        from anvil.api.v1.training import _validate_hparams

        # Should not raise any exception
        _validate_hparams(n_embd=16, n_head=4, _block_size=16)


######################################################################
# stream_training — gone case
######################################################################


@pytest.mark.asyncio
async def test_stream_training_run_gone(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /v1/training/stream/{run_id} when queue is None yields SSE error event."""
    from anvil.api.v1 import training as training_module

    mock_queue = None

    class MockTrainingService:
        """Minimal mock that returns None from get_queue."""

        def get_queue(self, run_id: int) -> None:  # type: ignore[misc]
            return mock_queue

        def release_queue(self, run_id: int) -> None:
            pass

    monkeypatch.setattr(training_module, "svc", MockTrainingService())

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="https://test",
        headers={"X-API-Key": get_api_key_store().key or ""},
    ) as client:
        async with client.stream("GET", "/v1/training/stream/1") as response:
            assert response.status_code == 200
            ct = response.headers.get("content-type", "")
            assert ct.startswith(
                "text/event-stream"
            ), f"Expected text/event-stream, got {ct}"

            body = await response.aread()
            text = body.decode()

    assert "event: error" in text
    assert "Training run has already completed" in text


######################################################################
# forward_pass_graph — 404
######################################################################


@pytest.mark.asyncio
async def test_forward_pass_graph_model_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /v1/forward-pass/graph returns 404 when InferenceService.load_model fails."""
    from anvil.api.v1 import training as training_module

    async def _raise_not_found(*args: object, **kwargs: object) -> object:
        raise FileNotFoundError("Demo model not found")

    monkeypatch.setattr(
        training_module.InferenceService,
        "load_model",
        _raise_not_found,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="https://test",
        headers={"X-API-Key": get_api_key_store().key or ""},
    ) as client:
        resp = await client.get("/v1/forward-pass/graph")

    assert resp.status_code == 404
    detail = resp.json().get("detail", "")
    assert "Demo model not found" in detail or "not found" in detail.lower()
