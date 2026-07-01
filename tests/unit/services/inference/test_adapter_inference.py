"""Unit tests for adapter inference composition in ``InferenceService``.

Tests the ``_compose_adapter`` method and the adapter path in
``load_model()``. Uses mocking for ``peft`` / ``transformers`` since
they are behind the ``[finetune]`` extra.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import anvil.services.inference.inference as inf_mod
from anvil.core.engine import LlamaModel
from anvil.services.inference.inference import InferenceService, _hf_to_anvil_key

# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def service() -> InferenceService:
    """Return an ``InferenceService`` with no adapter repo."""
    return InferenceService()


@pytest.fixture
def mock_adapter_repo() -> MagicMock:
    """Return a mock ``LoRAAdapterRepository`` with a fake adapter."""
    repo = MagicMock()
    adapter = MagicMock()
    adapter.adapter_id = "run_42"
    adapter.storage_path = "models/42/adapters/run_42/"
    adapter.external_model_id = 42
    repo.get_by_adapter_id = AsyncMock(return_value=adapter)
    return repo


@pytest.fixture
def mock_external_model() -> MagicMock:
    """Return a mock ``ExternalModel``."""
    m = MagicMock()
    m.id = 42
    m.source_identifier = "org/fake-model"
    return m


@pytest.fixture
def mock_ext_repo(mock_external_model: MagicMock) -> MagicMock:
    """Return a mock ``ExternalModelRepository``."""
    repo = MagicMock()
    repo.get = AsyncMock(return_value=mock_external_model)
    return repo


@pytest.fixture
def demo_model_path() -> str:
    """Return path to a real demo model for base-loading tests."""
    p = Path("data/models/experiment_1.json")
    if p.exists():
        return str(p)
    # Try fallback
    models_dir = Path("data/models")
    candidates = (
        sorted(models_dir.glob("experiment_*.json")) if models_dir.is_dir() else []
    )
    if candidates:
        return str(candidates[0])
    pytest.skip("No demo model found — cannot test base-only load")
    return ""


# ── Tests: _hf_to_anvil_key ─────────────────────────────────────────────


class TestHfToAnvilKey:
    """Unit tests for the HF→anvil key mapping function."""

    def test_top_level_keys(self):
        """Static top-level keys map correctly."""
        assert _hf_to_anvil_key("model.embed_tokens.weight") == "wte"
        assert _hf_to_anvil_key("lm_head.weight") == "lm_head"
        assert _hf_to_anvil_key("model.norm.weight") == "rms_final"

    def test_attention_keys(self):
        """Attention projection keys map correctly."""
        assert (
            _hf_to_anvil_key("model.layers.0.self_attn.q_proj.weight")
            == "layer0.attn_wq"
        )
        assert (
            _hf_to_anvil_key("model.layers.3.self_attn.k_proj.weight")
            == "layer3.attn_wk"
        )
        assert (
            _hf_to_anvil_key("model.layers.1.self_attn.v_proj.weight")
            == "layer1.attn_wv"
        )
        assert (
            _hf_to_anvil_key("model.layers.2.self_attn.o_proj.weight")
            == "layer2.attn_wo"
        )

    def test_mlp_keys(self):
        """MLP projection keys map correctly."""
        assert (
            _hf_to_anvil_key("model.layers.0.mlp.gate_proj.weight") == "layer0.mlp_gate"
        )
        assert _hf_to_anvil_key("model.layers.1.mlp.up_proj.weight") == "layer1.mlp_up"
        assert (
            _hf_to_anvil_key("model.layers.2.mlp.down_proj.weight") == "layer2.mlp_down"
        )

    def test_rmsnorm_keys(self):
        """RMSNorm scale keys map correctly."""
        assert (
            _hf_to_anvil_key("model.layers.0.input_layernorm.weight") == "layer0.rms_1"
        )
        assert (
            _hf_to_anvil_key("model.layers.0.post_attention_layernorm.weight")
            == "layer0.rms_2"
        )

    def test_unknown_key_returns_none(self):
        """Unrecognised keys return ``None``."""
        assert _hf_to_anvil_key("model.some_other.weight") is None
        assert _hf_to_anvil_key("foo.bar") is None
        assert _hf_to_anvil_key("layer0.foo.weight") is None


# ── Tests: load_model with adapter_id=None ───────────────────────────────


def _mock_base_load(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch the base-model load path so ``load_model`` never touches disk/MLflow.

    Makes ``data/models/experiment_{id}.json`` appear to exist and stubs
    ``LlamaModel.load`` + ``create_tokenizer`` so the base-only path is
    exercised deterministically without filesystem or network access.
    """
    fake_model = MagicMock()
    fake_model.chars = ["a", "b", "c"]
    fake_model.tokenizer_family = "char"
    fake_model.serialization_type = "char_json"
    monkeypatch.setattr(inf_mod.Path, "exists", lambda self: True)
    monkeypatch.setattr(inf_mod.LlamaModel, "load", staticmethod(lambda p: fake_model))
    monkeypatch.setattr(inf_mod, "create_tokenizer", lambda **kw: MagicMock())


class TestLoadModelBaseOnly:
    """Tests that ``load_model()`` without ``adapter_id`` works as before."""

    @pytest.mark.asyncio
    async def test_load_without_adapter_returns_base_model(
        self, service: InferenceService, monkeypatch: pytest.MonkeyPatch
    ):
        """``adapter_id=None`` returns a normally loaded model."""
        _mock_base_load(monkeypatch)
        loaded = await service.load_model(model_id=1, adapter_id=None)
        assert loaded is not None
        assert loaded.adapter_path is None
        assert loaded.model is not None

    @pytest.mark.asyncio
    async def test_load_model_with_explicit_id(
        self, service: InferenceService, monkeypatch: pytest.MonkeyPatch
    ):
        """Loading with explicit model_id and no adapter succeeds."""
        _mock_base_load(monkeypatch)
        loaded = await service.load_model(model_id=1)
        assert loaded is not None
        assert loaded.model_id == 1


# ── Tests: load_model with adapter_id (mocked) ───────────────────────────


class TestLoadModelWithAdapter:
    """Tests that ``load_model()`` with ``adapter_id`` composes adapters."""

    @pytest.mark.asyncio
    async def test_adapter_none_when_no_id(
        self, service: InferenceService, monkeypatch: pytest.MonkeyPatch
    ):
        """``adapter_path`` is ``None`` when no ``adapter_id`` given."""
        _mock_base_load(monkeypatch)
        loaded = await service.load_model(model_id=1)
        assert loaded.adapter_path is None

    @pytest.mark.asyncio
    async def test_missing_deps_raises_runtime_error(self):
        """If peft/transformers not installed, raise clear RuntimeError."""
        svc = InferenceService(adapter_repo=MagicMock())
        # Mock get_by_adapter_id returns an adapter
        svc._adapter_repo.get_by_adapter_id = AsyncMock(
            return_value=MagicMock(
                adapter_id="run_42",
                storage_path="models/42/adapters/run_42/",
                external_model_id=42,
            )
        )

        with (
            patch("anvil.services.inference.inference._PEFT_AVAILABLE", False),
            patch("anvil.services.inference.inference._TRANSFORMERS_AVAILABLE", False),
            pytest.raises(RuntimeError) as excinfo,
        ):
            await svc._compose_adapter(model_id=42, adapter_id="run_42")

        assert "pip install anvil[finetune]" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_unknown_adapter_raises_value_error(self):
        """Unknown adapter_id raises ValueError with helpful message."""
        repo = MagicMock()
        repo.get_by_adapter_id = AsyncMock(return_value=None)
        repo.get_by_model = AsyncMock(return_value=[])
        svc = InferenceService(adapter_repo=repo)

        with pytest.raises(ValueError) as excinfo:
            await svc._compose_adapter(model_id=42, adapter_id="nonexistent")

        assert "nonexistent" in str(excinfo.value)
        assert "not found" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_adapter_base_mismatch_raises_value_error(self):
        """Adapter-base shape mismatch raises ValueError."""
        repo = MagicMock()
        repo.get_by_adapter_id = AsyncMock(
            return_value=MagicMock(
                adapter_id="run_42",
                storage_path="models/42/adapters/run_42/",
                external_model_id=42,
            )
        )
        svc = InferenceService(adapter_repo=repo)

        # Mock ExternalModelRepository.get to return a dummy external model
        mock_ext = MagicMock()
        mock_ext.source_identifier = "org/fake-model"
        mock_ext.tokenizer_family = "subword"

        # Assign mocks to the module so _compose_adapter can find them
        inf_mod.AutoModelForCausalLM = MagicMock()
        inf_mod.PeftModel = MagicMock()
        inf_mod.PeftModel.from_pretrained = MagicMock(
            side_effect=ValueError("shape mismatch")
        )

        with (
            patch("anvil.services.inference.inference._PEFT_AVAILABLE", True),
            patch("anvil.services.inference.inference._TRANSFORMERS_AVAILABLE", True),
            patch(
                "anvil.services.inference.inference.ExternalModelRepository",
                return_value=MagicMock(get=AsyncMock(return_value=mock_ext)),
            ),
            pytest.raises(ValueError) as excinfo,
        ):
            await svc._compose_adapter(model_id=42, adapter_id="run_42")

        assert "shape mismatch" in str(excinfo.value) or "Failed to compose" in str(
            excinfo.value
        )

    @pytest.mark.asyncio
    async def test_successful_composition_returns_llama_model(self):
        """Successful adapter composition returns a ``LlamaModel``."""
        # Create a minimal real LlamaModel for the demo model path
        base_model = LlamaModel(
            vocab_size=8, n_embd=4, n_head=2, n_layer=1, block_size=8
        )
        base_model.chars = ["a", "b", "c", "d", "e", "f", "g", "h"]
        base_model.tokenizer_family = "char"
        base_model.serialization_type = "char_json"

        # Save to temp file so load_model can find it
        import json
        import tempfile

        tmp_dir = Path(tempfile.mkdtemp())
        model_path = tmp_dir / "experiment_1.json"
        base_model.save(str(model_path), chars=["a", "b", "c", "d", "e", "f", "g", "h"])

        # Mock external model
        ext_model = MagicMock()
        ext_model.id = 42
        ext_model.source_identifier = str(tmp_dir)  # dummy path

        ext_repo = MagicMock()
        ext_repo.get = AsyncMock(return_value=ext_model)

        # We'll patch to avoid actual HF loading
        # Instead, load the real anvil model and convert its state dict to HF format
        real_model = LlamaModel.load(str(model_path))

        # Create a mock HF model that mimics merge_and_unload()
        mock_hf_model = MagicMock()
        mock_hf_model.config = MagicMock()
        mock_hf_model.config.to_dict.return_value = {
            "vocab_size": 8,
            "hidden_size": 4,
            "num_hidden_layers": 1,
            "num_attention_heads": 2,
            "max_position_embeddings": 8,
            "intermediate_size": 10,
        }
        # merge_and_unload() should return the same mock (self)
        mock_hf_model.merge_and_unload.return_value = mock_hf_model

        # Build a state dict in HF format from the real model's state dict
        from anvil.services.training.export import export_state_dict

        hf_sd = export_state_dict(real_model)
        mock_hf_model.state_dict.return_value = hf_sd

        repo = MagicMock()
        repo.get_by_adapter_id = AsyncMock(
            return_value=MagicMock(
                adapter_id="run_42",
                storage_path=str(model_path),
                external_model_id=42,
            )
        )
        svc = InferenceService(adapter_repo=repo)

        # Mock ExternalModelRepository.get to return a dummy external model
        mock_ext = MagicMock()
        mock_ext.source_identifier = "org/fake-model"
        mock_ext.tokenizer_family = "subword"

        # Assign mocks to the module for the conditional imports
        inf_mod.AutoModelForCausalLM = MagicMock()
        inf_mod.AutoModelForCausalLM.from_pretrained = MagicMock(
            return_value=mock_hf_model
        )
        inf_mod.PeftModel = MagicMock()
        inf_mod.PeftModel.from_pretrained = MagicMock(return_value=mock_hf_model)

        with (
            patch("anvil.services.inference.inference._PEFT_AVAILABLE", True),
            patch("anvil.services.inference.inference._TRANSFORMERS_AVAILABLE", True),
            patch(
                "anvil.services.inference.inference.ExternalModelRepository",
                return_value=MagicMock(get=AsyncMock(return_value=mock_ext)),
            ),
        ):
            composed = await svc._compose_adapter(model_id=42, adapter_id="run_42")

        assert isinstance(composed, LlamaModel)
        assert composed.vocab_size == 8
        assert composed.n_embd == 4
        assert composed.n_layer == 1

        # Cleanup
        import shutil

        shutil.rmtree(tmp_dir)


# ── Tests: _compose_adapter with error paths ─────────────────────────────


class TestComposeAdapterErrors:
    """Error handling in ``_compose_adapter``."""

    @pytest.mark.asyncio
    async def test_peft_not_available(self):
        """Missing peft raises RuntimeError."""
        repo = MagicMock()
        repo.get_by_adapter_id = AsyncMock(
            return_value=MagicMock(
                adapter_id="run_42",
                storage_path="models/42/adapters/run_42/",
                external_model_id=42,
            )
        )
        svc = InferenceService(adapter_repo=repo)

        with (
            patch("anvil.services.inference.inference._PEFT_AVAILABLE", False),
            patch("anvil.services.inference.inference._TRANSFORMERS_AVAILABLE", True),
            pytest.raises(RuntimeError) as excinfo,
        ):
            await svc._compose_adapter(model_id=42, adapter_id="run_42")

        assert "peft" in str(excinfo.value).lower()

    @pytest.mark.asyncio
    async def test_transformers_not_available(self):
        """Missing transformers raises RuntimeError."""
        repo = MagicMock()
        repo.get_by_adapter_id = AsyncMock(
            return_value=MagicMock(
                adapter_id="run_42",
                storage_path="models/42/adapters/run_42/",
                external_model_id=42,
            )
        )
        svc = InferenceService(adapter_repo=repo)

        with (
            patch("anvil.services.inference.inference._PEFT_AVAILABLE", True),
            patch("anvil.services.inference.inference._TRANSFORMERS_AVAILABLE", False),
            pytest.raises(RuntimeError) as excinfo,
        ):
            await svc._compose_adapter(model_id=42, adapter_id="run_42")

        assert "pip install anvil[finetune]" in str(excinfo.value)


# ── Tests: C2 — session leak on singleton ──────────────────────────────────


class TestSessionLeak:
    """``_compose_adapter`` must not cache the DB session on the singleton."""

    @pytest.mark.asyncio
    async def test_no_repo_does_not_cache_session(self):
        """When no repo injected, session is scoped and not cached on self."""
        svc = InferenceService()  # no repo

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=Exception("DB error"))
        mock_session.close = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with (
            patch(
                "anvil.services.inference.inference.AsyncSessionLocal",
                return_value=mock_session,
            ),
            pytest.raises(Exception),
        ):
            await svc._compose_adapter(model_id=42, adapter_id="nonexistent")

        # Singleton MUST NOT cache the repo/session
        assert svc._adapter_repo is None
        # Session was entered and exited via async context manager
        mock_session.__aenter__.assert_called_once()
        mock_session.__aexit__.assert_called_once()

    @pytest.mark.asyncio
    async def test_injected_repo_no_session_created(self):
        """When repo was injected, no self-managed session is created."""
        repo = MagicMock()
        repo.get_by_adapter_id = AsyncMock(return_value=None)
        repo.get_by_model = AsyncMock(return_value=[])
        svc = InferenceService(adapter_repo=repo)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with (
            patch(
                "anvil.services.inference.inference.AsyncSessionLocal",
                return_value=mock_session,
            ),
            pytest.raises(ValueError),
        ):
            await svc._compose_adapter(model_id=42, adapter_id="nonexistent")

        # No self-managed session should have been created since repo was injected
        mock_session.__aenter__.assert_not_called()


# ── Tests: H1 — unknown adapter lists real IDs ────────────────────────────


class TestUnknownAdapterListsRealIds:
    """``_compose_adapter`` must list real available adapter IDs on error."""

    @pytest.mark.asyncio
    async def test_lists_available_adapters(self):
        """Error message includes real adapter IDs from the DB."""
        repo = MagicMock()
        repo.get_by_adapter_id = AsyncMock(return_value=None)
        repo.get_by_model = AsyncMock(
            return_value=[
                MagicMock(adapter_id="run_1"),
                MagicMock(adapter_id="run_2"),
            ]
        )
        svc = InferenceService(adapter_repo=repo)

        with pytest.raises(ValueError) as excinfo:
            await svc._compose_adapter(model_id=42, adapter_id="nonexistent")

        assert "run_1" in str(excinfo.value)
        assert "run_2" in str(excinfo.value)
        assert "Available adapters" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_empty_list_when_no_adapters(self):
        """Error message shows empty list when no adapters exist."""
        repo = MagicMock()
        repo.get_by_adapter_id = AsyncMock(return_value=None)
        repo.get_by_model = AsyncMock(return_value=[])
        svc = InferenceService(adapter_repo=repo)

        with pytest.raises(ValueError) as excinfo:
            await svc._compose_adapter(model_id=42, adapter_id="nonexistent")

        assert "Available adapters: []" in str(excinfo.value)
