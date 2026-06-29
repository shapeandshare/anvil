# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for eval API endpoints.

Covers perplexity computation via /v1/eval/perplexity.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from anvil.services.inference.inference import InferenceService


class TestEvalPerplexity:
    """Tests for POST /v1/eval/perplexity."""

    @pytest.fixture
    def mock_model(self):
        """Create a mock loaded model for testing perplexity."""
        model = MagicMock()
        model.vocab_size = 10
        model.n_embd = 16
        model.n_head = 4
        model.n_layer = 1
        model.block_size = 16
        return model

    @pytest.fixture
    def mock_loaded(self, mock_model):
        """Create a mock loaded model result with chars."""
        loaded = MagicMock()
        loaded.model = mock_model
        # chars = list of unique chars for vocabulary
        loaded.chars = list("abcdefghij")  # 10 chars matching vocab_size
        return loaded

    async def test_perplexity_computed_successfully(self, client, mock_loaded):
        """Happy path: perplexity computed for a valid model and text."""
        class FakeValue:
            data = 0.5
            def log(self):
                return FakeValue()
            def __neg__(self):
                return FakeValue()

        fake_value = FakeValue()

        with (
            patch.object(
                InferenceService,
                "load_model",
                return_value=mock_loaded,
            ),
            patch("anvil.api.v1.eval.softmax", return_value=[fake_value] * 10),
        ):
            resp = await client.post(
                "/v1/eval/perplexity",
                json={
                    "model_id": 1,
                    "version": 1,
                    "text": "abc",
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "perplexity" in data
        assert data["perplexity"] > 0
        assert "avg_loss" in data
        assert data["avg_loss"] > 0
        assert data["num_positions"] > 0
        assert data["vocab_size"] == 10
        assert "model_config" in data
        assert data["model_config"]["n_layer"] == 1
        assert data["model_config"]["n_embd"] == 16
        assert data["model_config"]["n_head"] == 4
        assert data["model_config"]["block_size"] == 16

    async def test_returns_404_when_model_not_found(self, client):
        """Returns 404 when the model is not found."""
        with patch.object(
            InferenceService,
            "load_model",
            side_effect=ValueError("Model not found"),
        ):
            resp = await client.post(
                "/v1/eval/perplexity",
                json={
                    "model_id": 999,
                    "version": 1,
                    "text": "abc",
                },
            )
        assert resp.status_code == 404
        assert "Model not found" in resp.json()["detail"]

    async def test_returns_404_on_file_not_found(self, client):
        """Returns 404 when the model file is not found."""
        with patch.object(
            InferenceService,
            "load_model",
            side_effect=FileNotFoundError("model file missing"),
        ):
            resp = await client.post(
                "/v1/eval/perplexity",
                json={
                    "model_id": 1,
                    "version": 1,
                    "text": "abc",
                },
            )
        assert resp.status_code == 404
        assert "model file missing" in resp.json()["detail"]

    async def test_returns_400_for_char_out_of_vocab(self, client, mock_loaded):
        """Returns 400 when text contains a character not in vocabulary."""
        with patch.object(
            InferenceService,
            "load_model",
            return_value=mock_loaded,
        ):
            resp = await client.post(
                "/v1/eval/perplexity",
                json={
                    "model_id": 1,
                    "version": 1,
                    "text": "xyz!",
                },
            )
        assert resp.status_code == 400
        assert "not in model vocabulary" in resp.json()["detail"]

    async def test_validates_required_fields(self, client):
        """Pydantic validation: missing fields return 422."""
        resp = await client.post(
            "/v1/eval/perplexity",
            json={"text": "abc"},
        )
        assert resp.status_code == 422

    async def test_validates_empty_text(self, client):
        """Pydantic validation: empty text returns 422."""
        resp = await client.post(
            "/v1/eval/perplexity",
            json={"model_id": 1, "version": 1, "text": ""},
        )
        assert resp.status_code == 422

    async def test_validates_extra_fields_forbidden(self, client):
        """Pydantic validation: extra fields are forbidden."""
        resp = await client.post(
            "/v1/eval/perplexity",
            json={
                "model_id": 1,
                "version": 1,
                "text": "abc",
                "extra": "field",
            },
        )
        assert resp.status_code == 422