"""End-to-end tests for adapter inference via the generate endpoint.

Tests that ``POST /v1/inference/generate`` works both with and without
an ``adapter_id``, and returns appropriate HTTP errors for unknown
adapter IDs. The inference service is mocked so no real HuggingFace /
peft dependencies are exercised.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from anvil.services.inference.loaded_model import LoadedModel

# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _mock_svc():
    """Replace the module-level ``_svc`` with a mock for all tests."""
    with patch("anvil.api.v1.inference._svc") as mock_svc:
        yield mock_svc


# ── Helpers ──────────────────────────────────────────────────────────────


def _build_dummy_tokenizer():
    """Build a minimal tokenizer mock that mimics char-level encoding."""
    tok = MagicMock()
    tok.encode.return_value = [1, 2, 3]
    tok.decode.return_value = "generated output"
    tok.vocab_size = 8
    tok.bos_id = 1
    tok.chars = ["a", "b", "c", "d", "e", "f", "g", "h"]
    return tok


def _make_loaded(adapter_path: str | None = None) -> LoadedModel:
    """Build a ``LoadedModel`` with a mocked model and tokenizer."""
    return LoadedModel(
        model=MagicMock(),
        tokenizer=_build_dummy_tokenizer(),
        model_id=1,
        version=1,
        name="test",
        adapter_path=adapter_path,
    )


# ── Tests: without adapter_id ────────────────────────────────────────────


class TestGenerateWithoutAdapter:
    """Tests for base-only (``adapter_id=None``) generation."""

    @pytest.mark.asyncio
    async def test_generate_without_adapter_returns_text(self, client):
        """``POST /v1/inference/generate`` without ``adapter_id`` works."""
        with patch("anvil.api.v1.inference._svc") as mock_svc:
            mock_svc.load_model = AsyncMock(return_value=_make_loaded())
            mock_svc.generate = MagicMock(return_value="hello world")

            resp = await client.post(
                "/v1/inference/generate",
                json={"model_id": 1, "prompt": "hello", "max_tokens": 10},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["text"] == "hello world"
        assert "adapter_id" not in data

    @pytest.mark.asyncio
    async def test_generate_passes_adapter_id_none(self, client):
        """Without ``adapter_id``, ``load_model`` receives ``None``."""
        with patch("anvil.api.v1.inference._svc") as mock_svc:
            mock_svc.load_model = AsyncMock(return_value=_make_loaded())
            mock_svc.generate = MagicMock(return_value="output")

            await client.post(
                "/v1/inference/generate",
                json={"model_id": 1, "prompt": "hello"},
            )

        mock_svc.load_model.assert_called_once_with(model_id=1, adapter_id=None)


# ── Tests: with adapter_id ───────────────────────────────────────────────


class TestGenerateWithAdapter:
    """Tests for adapter composition generation."""

    @pytest.mark.asyncio
    async def test_generate_with_adapter_returns_text(self, client):
        """``POST /v1/inference/generate`` with ``adapter_id`` works."""
        with patch("anvil.api.v1.inference._svc") as mock_svc:
            mock_svc.load_model = AsyncMock(
                return_value=_make_loaded(adapter_path="models/1/adapters/run_42/")
            )
            mock_svc.generate = MagicMock(return_value="adapted output")

            resp = await client.post(
                "/v1/inference/generate",
                json={"model_id": 1, "prompt": "hello", "adapter_id": "run_42"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["text"] == "adapted output"
        assert data.get("adapter_id") == "run_42"

    @pytest.mark.asyncio
    async def test_generate_passes_adapter_id(self, client):
        """With ``adapter_id``, ``load_model`` receives the ID."""
        with patch("anvil.api.v1.inference._svc") as mock_svc:
            mock_svc.load_model = AsyncMock(
                return_value=_make_loaded(adapter_path="models/1/adapters/run_42/")
            )
            mock_svc.generate = MagicMock(return_value="output")

            await client.post(
                "/v1/inference/generate",
                json={"model_id": 1, "prompt": "hello", "adapter_id": "run_42"},
            )

        mock_svc.load_model.assert_called_once_with(model_id=1, adapter_id="run_42")

    @pytest.mark.asyncio
    async def test_adapter_included_in_response(self, client):
        """Adapter ID appears in the response JSON."""
        with patch("anvil.api.v1.inference._svc") as mock_svc:
            mock_svc.load_model = AsyncMock(
                return_value=_make_loaded(adapter_path="models/1/adapters/run_42/")
            )

            resp = await client.post(
                "/v1/inference/generate",
                json={"model_id": 1, "prompt": "hello", "adapter_id": "run_42"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data.get("adapter_id") == "run_42"
        assert data.get("model_id") == 1


# ── Tests: error paths ───────────────────────────────────────────────────


class TestGenerateErrorPaths:
    """Error handling in the generate endpoint."""

    @pytest.mark.asyncio
    async def test_unknown_adapter_returns_404(self, client):
        """Unknown ``adapter_id`` returns HTTP 404 with detail."""
        with patch("anvil.api.v1.inference._svc") as mock_svc:
            mock_svc.load_model = AsyncMock(
                side_effect=ValueError(
                    "Adapter 'nonexistent' not found for model 1. "
                    "Available adapters: []"
                )
            )

            resp = await client.post(
                "/v1/inference/generate",
                json={
                    "model_id": 1,
                    "prompt": "hello",
                    "adapter_id": "nonexistent",
                },
            )

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_missing_base_model_returns_404(self, client):
        """Missing base model returns HTTP 404."""
        with patch("anvil.api.v1.inference._svc") as mock_svc:
            mock_svc.load_model = AsyncMock(
                side_effect=ValueError("Model not found: model_id=999, version=1")
            )

            resp = await client.post(
                "/v1/inference/generate",
                json={"model_id": 999, "prompt": "hello"},
            )

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_missing_deps_returns_500(self, client):
        """Missing peft/transformers returns HTTP 500."""
        with patch("anvil.api.v1.inference._svc") as mock_svc:
            mock_svc.load_model = AsyncMock(
                side_effect=RuntimeError(
                    "Adapter inference requires peft, torch, and transformers. "
                    "Install: pip install anvil[finetune]"
                )
            )

            resp = await client.post(
                "/v1/inference/generate",
                json={"model_id": 1, "prompt": "hello", "adapter_id": "run_42"},
            )

        assert resp.status_code == 500
