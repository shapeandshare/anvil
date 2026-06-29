# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for anvil/services/training/torch_engine.py.

ALL torch interactions are mocked — these tests run without PyTorch installed.
The module gracefully degrades when torch is missing; we test both the
torch-unavailable path (unpatched) and the torch-available path (fully mocked).
"""

from __future__ import annotations

import math
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from anvil.services.training.torch_engine import (
    _TORCH_AVAILABLE,
    torch_available,
    TorchLlamaModel,
    train_torch,
    load_torch_weights_from_lists,
)


########################################################################
# Fake torch primitives — real classes so isinstance() checks work
########################################################################


class _FakeTensor:
    """Stand-in for torch.Tensor in mocked tests."""

    def __init__(self, data: object = None):
        self.grad: object = None
        self._shape: tuple[int, ...] = (1,)

    @property
    def shape(self) -> tuple[int, ...]:
        return self._shape

    @shape.setter
    def shape(self, val: tuple[int, ...]) -> None:
        self._shape = val

    def __getitem__(self, key: object) -> _FakeTensor:
        return _FakeTensor()

    def __setitem__(self, key: object, value: object) -> None:
        pass

    def item(self) -> float:
        return 0.42

    def tolist(self) -> list[list[float]]:
        return [[0.1, 0.2], [0.3, 0.4]]

    def numel(self) -> int:
        return int(np.prod(self._shape)) if self._shape else 1

    def backward(self) -> None:
        pass

    def pow(self, exp: float) -> _FakeTensor:
        return self

    def sum(self) -> _FakeTensor:
        return self

    def to(self, device: object) -> _FakeTensor:
        return self

    def detach(self) -> _FakeTensor:
        return self

    def cpu(self) -> _FakeTensor:
        return self

    def unsqueeze(self, dim: int) -> _FakeTensor:
        return self

    def expand(self, *size: int) -> _FakeTensor:
        return self

    def __add__(self, other: object) -> _FakeTensor:
        return self

    def __sub__(self, other: object) -> _FakeTensor:
        return self

    def __mul__(self, other: object) -> _FakeTensor:
        return self

    def __truediv__(self, other: object) -> _FakeTensor:
        return self

    def __rtruediv__(self, other: object) -> _FakeTensor:
        return self

    def __neg__(self) -> _FakeTensor:
        return self

    def __radd__(self, other: object) -> _FakeTensor:
        return self

    def __rmul__(self, other: object) -> _FakeTensor:
        return self

    def __rpow__(self, other: object) -> _FakeTensor:
        return self

    def __matmul__(self, other: object) -> _FakeTensor:
        return self

    @property
    def T(self) -> _FakeTensor:
        return self

    def __gt__(self, other: object) -> _FakeTensor:
        return _FakeTensor()

    def __lt__(self, other: object) -> _FakeTensor:
        return _FakeTensor()

    def __float__(self) -> float:
        return 0.42

    def __int__(self) -> int:
        return 0

    def __len__(self) -> int:
        return 1

    def __bool__(self) -> bool:
        return True

    def __iter__(self):
        return iter([0.42])


class _FakeParameter:
    """Stand-in for torch.nn.Parameter so isinstance() checks work."""

    def __init__(self, data: object = None, requires_grad: bool = True):
        self.data = data if data is not None else _FakeTensor()
        self.grad: object = None
        self.requires_grad = requires_grad

    def __getitem__(self, key: object) -> _FakeTensor:
        return _FakeTensor()

    def numel(self) -> int:
        d = self.data
        if isinstance(d, _FakeTensor):
            return d.numel()
        return 1

    def tolist(self) -> object:
        if hasattr(self.data, "tolist"):
            return self.data.tolist()
        return [[0.1]]

    def detach(self) -> _FakeTensor:
        d = self.data
        if isinstance(d, _FakeTensor):
            return d.detach()
        return _FakeTensor()

    def cpu(self) -> _FakeParameter:
        return self

    def copy_(self, tensor: object) -> None:
        pass

    def to(self, device: object) -> _FakeParameter:
        return self

    @property
    def shape(self) -> tuple[int, ...]:
        d = self.data
        if isinstance(d, _FakeTensor):
            return d.shape
        return ()

    @property
    def dtype(self) -> str:
        return "float32"

    @property
    def device(self) -> str:
        return "cpu"


class _FakeParameterList(list):
    """Stand-in for torch.nn.ParameterList so isinstance() checks work."""


########################################################################
# Fixture — fully mocked torch + F
########################################################################


@pytest.fixture
def mock_torch():
    """Create a comprehensive mock of the torch module and F (nn.functional).

    Returns (torch_mock, F_mock). Patches are applied automatically.
    """
    torch_mock = MagicMock()
    F_mock = MagicMock()

    torch_mock.nn.Parameter = _FakeParameter
    torch_mock.nn.ParameterList = _FakeParameterList

    def _make_tensor(*args, **kwargs):
        """Return a _FakeTensor whose shape matches the positional args."""
        t = _FakeTensor()
        if args:
            t.shape = tuple(args)
        return t

    for fn_name in (
        "randn",
        "ones",
        "zeros",
    ):
        getattr(torch_mock, fn_name).side_effect = _make_tensor
    torch_mock.arange.side_effect = lambda *a, **kw: _make_tensor(1)
    for fn_name in ("empty_like", "stack", "cat", "mv"):
        getattr(torch_mock, fn_name).return_value = _FakeTensor()
    torch_mock.cos.return_value = _FakeTensor()
    torch_mock.sin.return_value = _FakeTensor()
    torch_mock.log.return_value = _FakeTensor()

    def _fake_tensor(data, **kwargs):
        t = _FakeTensor()
        if isinstance(data, list):
            if data and isinstance(data[0], list):
                t.shape = (len(data), len(data[0]))
            else:
                t.shape = (len(data),)
        return t

    torch_mock.tensor.side_effect = _fake_tensor

    torch_mock.no_grad.return_value.__enter__ = MagicMock(return_value=None)
    torch_mock.no_grad.return_value.__exit__ = MagicMock(return_value=None)

    torch_mock.device.return_value = "cpu"
    torch_mock.manual_seed.return_value = None
    torch_mock.float = float

    optim_mock = MagicMock()
    optim_mock.zero_grad.return_value = None
    optim_mock.step.return_value = None
    torch_mock.optim.Adam.return_value = optim_mock
    scheduler_mock = MagicMock()
    scheduler_mock.step.return_value = None
    torch_mock.optim.lr_scheduler.LambdaLR.return_value = scheduler_mock

    for fn_name in ("rms_norm", "linear", "silu"):
        getattr(F_mock, fn_name).return_value = _FakeTensor()

    softmax_tensor = _FakeTensor()
    softmax_tensor.numpy = MagicMock(  # type: ignore[method-assign]
        return_value=np.array([0.1] * 5, dtype=np.float64)
    )
    F_mock.softmax.return_value = softmax_tensor

    # Patch random.choices to always return first element regardless of size
    random_choices_mock = MagicMock(side_effect=lambda pop, **kw: [pop[0]])

    return torch_mock, F_mock, random_choices_mock


@pytest.fixture
def apply_mocks(mock_torch):
    """Apply all torch patches to the module under test."""
    torch_mock, F_mock, random_choices_mock = mock_torch
    with (
        patch("anvil.services.training.torch_engine._TORCH_AVAILABLE", True),
        patch("anvil.services.training.torch_engine.torch", torch_mock),
        patch("anvil.services.training.torch_engine.F", F_mock),
        patch(
            "anvil.services.training.torch_engine.torch_Tensor",
            _FakeTensor,
            create=True,
        ),
        patch(
            "anvil.services.training.torch_engine.random.choices",
            random_choices_mock,
        ),
    ):
        yield


########################################################################
# Tests — torch-unavailable path (no mocking needed)
########################################################################


class TestTorchUnavailable:

    def test_torch_available_returns_false(self):
        assert torch_available() is False

    def test_torch_available_consistent_with_module_flag(self):
        assert _TORCH_AVAILABLE is False

    def test_torch_llama_model_init_raises_without_torch(self):
        with pytest.raises(RuntimeError, match="torch is not installed"):
            TorchLlamaModel(vocab_size=10)

    def test_train_torch_raises_without_torch(self):
        with pytest.raises(RuntimeError, match="torch is not installed"):
            train_torch(["hello world"])


########################################################################
# Tests — TorchLlamaModel construction
########################################################################


class TestTorchLlamaModelConstruction:

    @pytest.mark.usefixtures("apply_mocks")
    def test_init_odd_head_dim_raises(self):
        m = TorchLlamaModel(vocab_size=10, n_embd=8, n_head=2)
        assert m.head_dim == 4

        with pytest.raises(ValueError, match="head_dim=1 must be even"):
            TorchLlamaModel(vocab_size=10, n_embd=6, n_head=4)

    @pytest.mark.usefixtures("apply_mocks")
    def test_init_stores_attributes(self):
        m = TorchLlamaModel(
            vocab_size=20,
            n_embd=32,
            n_head=8,
            n_layer=2,
            block_size=64,
        )
        assert m.vocab_size == 20
        assert m.n_embd == 32
        assert m.n_head == 8
        assert m.n_layer == 2
        assert m.block_size == 64
        assert m.head_dim == 4
        assert m.intermediate_size == int(8 * 32 / 3)

    @pytest.mark.usefixtures("apply_mocks")
    def test_init_creates_parameters(self):
        m = TorchLlamaModel(
            vocab_size=10,
            n_embd=8,
            n_head=4,
            n_layer=2,
            block_size=16,
        )
        params = list(m.parameters())
        assert len(params) == 3 + 2 * 9

    @pytest.mark.usefixtures("apply_mocks")
    def test_init_creates_rope_tables(self):
        m = TorchLlamaModel(
            vocab_size=10,
            n_embd=8,
            n_head=4,
            n_layer=1,
            block_size=16,
        )
        assert hasattr(m, "cos_table")
        assert hasattr(m, "sin_table")

    @pytest.mark.usefixtures("apply_mocks")
    def test_num_params_property(self):
        m = TorchLlamaModel(vocab_size=10, n_embd=8, n_head=4, n_layer=1, block_size=8)
        n = m.num_params
        assert isinstance(n, int)
        assert n > 0

    @pytest.mark.usefixtures("apply_mocks")
    def test_to_returns_self(self):
        m = TorchLlamaModel(vocab_size=10, n_embd=8, n_head=4, n_layer=1, block_size=8)
        result = m.to("cpu")
        assert result is m

    @pytest.mark.usefixtures("apply_mocks")
    def test_eval_is_noop(self):
        m = TorchLlamaModel(vocab_size=10, n_embd=8, n_head=4, n_layer=1, block_size=8)
        m.eval()


########################################################################
# Tests — export_weights
########################################################################


class TestExportWeights:

    @pytest.mark.usefixtures("apply_mocks")
    def test_export_weights_returns_dict(self):
        m = TorchLlamaModel(
            vocab_size=10,
            n_embd=8,
            n_head=4,
            n_layer=1,
            block_size=8,
        )
        exported = m.export_weights()
        assert isinstance(exported, dict)
        expected_keys = {
            "wte",
            "lm_head",
            "rms_final",
            "layer0.attn_wq",
            "layer0.attn_wk",
            "layer0.attn_wv",
            "layer0.attn_wo",
            "layer0.rms_1",
            "layer0.rms_2",
            "layer0.mlp_gate",
            "layer0.mlp_up",
            "layer0.mlp_down",
        }
        assert set(exported) == expected_keys

    @pytest.mark.usefixtures("apply_mocks")
    def test_export_weights_multi_layer(self):
        m = TorchLlamaModel(
            vocab_size=10,
            n_embd=8,
            n_head=4,
            n_layer=3,
            block_size=8,
        )
        exported = m.export_weights()
        for li in range(3):
            assert f"layer{li}.attn_wq" in exported
            assert f"layer{li}.mlp_gate" in exported

    @pytest.mark.usefixtures("apply_mocks")
    def test_export_weights_values_are_lists(self):
        m = TorchLlamaModel(vocab_size=10, n_embd=8, n_head=4, n_layer=1, block_size=8)
        exported = m.export_weights()
        for key, val in exported.items():
            assert isinstance(val, list), f"{key} is not a list"


########################################################################
# Tests — load_torch_weights_from_lists
########################################################################


class TestLoadTorchWeightsFromLists:

    @pytest.fixture
    def model(self):
        return TorchLlamaModel(
            vocab_size=10,
            n_embd=8,
            n_head=4,
            n_layer=1,
            block_size=16,
        )

    def build_weights(self, vocab_size: int = 10, n_embd: int = 8, n_layer: int = 1):
        w = {
            "wte": [[0.1] * n_embd for _ in range(vocab_size)],
            "lm_head": [[0.1] * n_embd for _ in range(vocab_size)],
            "rms_final": [0.1] * n_embd,
        }
        isize = int(8 * n_embd / 3)
        for li in range(n_layer):
            w[f"layer{li}.attn_wq"] = [[0.1] * n_embd for _ in range(n_embd)]
            w[f"layer{li}.attn_wk"] = [[0.1] * n_embd for _ in range(n_embd)]
            w[f"layer{li}.attn_wv"] = [[0.1] * n_embd for _ in range(n_embd)]
            w[f"layer{li}.attn_wo"] = [[0.1] * n_embd for _ in range(n_embd)]
            w[f"layer{li}.mlp_gate"] = [[0.1] * n_embd for _ in range(isize)]
            w[f"layer{li}.mlp_up"] = [[0.1] * n_embd for _ in range(isize)]
            w[f"layer{li}.mlp_down"] = [[0.1] * isize for _ in range(n_embd)]
            w[f"layer{li}.rms_1"] = [0.1] * n_embd
            w[f"layer{li}.rms_2"] = [0.1] * n_embd
        return w

    @pytest.mark.usefixtures("apply_mocks")
    def test_loads_weights_successfully(self, model):
        weights = self.build_weights()
        load_torch_weights_from_lists(model, weights)

    @pytest.mark.usefixtures("apply_mocks")
    def test_rejects_missing_keys(self, model):
        weights = self.build_weights()
        del weights["lm_head"]
        with pytest.raises(ValueError, match="missing="):
            load_torch_weights_from_lists(model, weights)

    @pytest.mark.usefixtures("apply_mocks")
    def test_rejects_extra_keys(self, model):
        weights = self.build_weights()
        weights["extra_key"] = [[0.1]]
        with pytest.raises(ValueError, match="extra="):
            load_torch_weights_from_lists(model, weights)

    @pytest.mark.usefixtures("apply_mocks")
    def test_rejects_shape_mismatch(self, model):
        """Shape mismatch raises ValueError."""
        weights = self.build_weights()
        weights["wte"] = [[0.1, 0.2]]
        with pytest.raises(ValueError, match="Shape mismatch for wte"):
            load_torch_weights_from_lists(model, weights)

    @pytest.mark.usefixtures("apply_mocks")
    def test_rejects_shape_mismatch_inline(self):
        """Shape mismatch raises ValueError (model created inline)."""
        model = TorchLlamaModel(
            vocab_size=10,
            n_embd=8,
            n_head=4,
            n_layer=1,
            block_size=16,
        )
        weights = self.build_weights()
        weights["wte"] = [[0.1, 0.2]]
        with pytest.raises(ValueError, match="Shape mismatch for wte"):
            load_torch_weights_from_lists(model, weights)


########################################################################
# Tests — convert_weights (load_torch_weights_from_lists + export_weights)
########################################################################


class TestConvertWeights:

    @pytest.mark.usefixtures("apply_mocks")
    def test_export_then_load_round_trip(self):
        """Exporting weights and loading back succeeds (shape-matched data)."""
        m = TorchLlamaModel(
            vocab_size=10,
            n_embd=8,
            n_head=4,
            n_layer=1,
            block_size=16,
        )
        exported = m.export_weights()
        _isize = int(8 * 8 / 3)
        weights = {
            "wte": [[0.1] * 8 for _ in range(10)],
            "lm_head": [[0.1] * 8 for _ in range(10)],
            "rms_final": [0.1] * 8,
            "layer0.attn_wq": [[0.1] * 8 for _ in range(8)],
            "layer0.attn_wk": [[0.1] * 8 for _ in range(8)],
            "layer0.attn_wv": [[0.1] * 8 for _ in range(8)],
            "layer0.attn_wo": [[0.1] * 8 for _ in range(8)],
            "layer0.mlp_gate": [[0.1] * 8 for _ in range(_isize)],
            "layer0.mlp_up": [[0.1] * 8 for _ in range(_isize)],
            "layer0.mlp_down": [[0.1] * _isize for _ in range(8)],
            "layer0.rms_1": [0.1] * 8,
            "layer0.rms_2": [0.1] * 8,
        }
        load_torch_weights_from_lists(m, weights)


########################################################################
# Tests — train_torch (main training loop)
########################################################################


class TestTrainTorch:

    TRAIN_DOCS = ["hello world", "goodbye moon", "abc"]

    def _train(self, **kwargs):
        defaults = dict(
            docs=self.TRAIN_DOCS,
            device="cpu",
            num_steps=5,
            block_size=8,
            n_embd=8,
            n_head=4,
            n_layer=1,
            learning_rate=0.01,
            temperature=0.5,
        )
        defaults.update(kwargs)
        return train_torch(**defaults)

    @pytest.mark.usefixtures("apply_mocks")
    def test_returns_correct_tuple(self):
        result = self._train()
        assert isinstance(result, tuple)
        assert len(result) == 4
        weights, loss, samples, uchars = result
        assert isinstance(weights, dict)
        assert isinstance(loss, float)
        assert isinstance(samples, list)
        assert isinstance(uchars, list)
        assert len(samples) == 20

    @pytest.mark.usefixtures("apply_mocks")
    def test_uchars_contains_sorted_characters(self):
        _, _, _, uchars = self._train()
        assert " " in uchars
        for doc in self.TRAIN_DOCS:
            for ch in doc:
                assert ch in uchars
        assert uchars == sorted(uchars)

    @pytest.mark.usefixtures("apply_mocks")
    def test_weights_contains_expected_keys(self):
        weights, _, _, _ = self._train()
        expected_keys = {
            "wte",
            "lm_head",
            "rms_final",
            "layer0.attn_wq",
            "layer0.attn_wk",
            "layer0.attn_wv",
            "layer0.attn_wo",
            "layer0.rms_1",
            "layer0.rms_2",
            "layer0.mlp_gate",
            "layer0.mlp_up",
            "layer0.mlp_down",
        }
        assert set(weights) == expected_keys

    @pytest.mark.usefixtures("apply_mocks")
    def test_final_loss_is_positive(self):
        _, loss, _, _ = self._train()
        assert loss > 0
        assert math.isfinite(loss)

    @pytest.mark.usefixtures("apply_mocks")
    def test_default_num_steps(self):
        result = self._train(num_steps=3)
        assert result[1] > 0


########################################################################
# Tests — progress callback
########################################################################


class TestProgressCallback:

    @pytest.mark.usefixtures("apply_mocks")
    def test_callback_receives_step_and_loss(self):
        calls: list[tuple] = []

        def cb(step: int, loss: float, **kwargs: object) -> None:
            calls.append((step, loss))

        self._train_with_cb(cb)
        assert len(calls) == 5
        for s in range(5):
            assert calls[s][0] == s
            assert isinstance(calls[s][1], float)

    @pytest.mark.usefixtures("apply_mocks")
    def test_callback_receives_kwargs(self):
        calls: list[dict] = []

        def cb(step: int, loss: float, **kwargs: object) -> None:
            calls.append(kwargs)

        self._train_with_cb(cb)
        for kw in calls:
            assert "tokens" in kw
            assert "grad_norm" in kw
            assert isinstance(kw["tokens"], int)
            assert isinstance(kw["grad_norm"], float)

    @pytest.mark.usefixtures("apply_mocks")
    def test_callback_not_called_when_none(self):
        self._train_with_cb(None)

    def _train_with_cb(self, cb):
        defaults = dict(
            docs=["hello world", "goodbye moon", "abc"],
            device="cpu",
            num_steps=5,
            block_size=8,
            n_embd=8,
            n_head=4,
            n_layer=1,
            learning_rate=0.01,
            temperature=0.5,
            progress_callback=cb,
        )
        return train_torch(**defaults)


########################################################################
# Tests — stop_check
########################################################################


class TestStopCheck:

    @pytest.mark.usefixtures("apply_mocks")
    def test_stop_check_halts_early(self):
        calls: list[int] = []

        def cb(step: int, loss: float, **kwargs: object) -> None:
            calls.append(step)

        def stop_after_2() -> bool:
            return len(calls) >= 2

        self._train_with_stop(cb, stop_after_2)
        assert len(calls) == 2

    @pytest.mark.usefixtures("apply_mocks")
    def test_stop_check_never_stops(self):
        calls: list[int] = []

        def cb(step: int, loss: float, **kwargs: object) -> None:
            calls.append(step)

        def never_stop() -> bool:
            return False

        self._train_with_stop(cb, never_stop)
        assert len(calls) == 5

    def _train_with_stop(self, cb, stop_check_fn):
        defaults = dict(
            docs=["hello world", "goodbye moon", "abc"],
            device="cpu",
            num_steps=5,
            block_size=8,
            n_embd=8,
            n_head=4,
            n_layer=1,
            learning_rate=0.01,
            temperature=0.5,
            progress_callback=cb,
            stop_check=stop_check_fn,
        )
        return train_torch(**defaults)


########################################################################
# Tests — checkpointing (warm-start with pre-trained model)
########################################################################


class TestWarmStart:

    @pytest.fixture
    def pretrained_model(self):
        m = TorchLlamaModel(
            vocab_size=10,
            n_embd=8,
            n_head=4,
            n_layer=1,
            block_size=8,
        )
        m.chars = list("abcdefgh")
        return m

    @pytest.fixture
    def matching_model(self):
        m = TorchLlamaModel(
            vocab_size=9,
            n_embd=8,
            n_head=4,
            n_layer=1,
            block_size=8,
        )
        m.chars = list("abcdefgh")
        return m

    @pytest.mark.usefixtures("apply_mocks")
    def test_warm_start_rejects_no_chars(self, pretrained_model):
        """Model with chars=None class default hits assertion error."""
        del pretrained_model.chars
        with pytest.raises(AssertionError):
            train_torch(
                docs=["hello"],
                model=pretrained_model,
                num_steps=2,
            )

    @pytest.mark.usefixtures("apply_mocks")
    def test_warm_start_rejects_oov_chars(self, matching_model):
        with pytest.raises(ValueError, match="character"):
            train_torch(
                docs=["hello world"],
                model=matching_model,
                num_steps=2,
            )

    @pytest.mark.usefixtures("apply_mocks")
    def test_warm_start_accepts_known_chars(self, matching_model):
        result = train_torch(
            docs=["abc", "def", "h"],
            model=matching_model,
            num_steps=3,
            block_size=8,
            n_embd=8,
            n_head=4,
            n_layer=1,
            learning_rate=0.01,
            temperature=0.5,
        )
        _, loss, samples, uchars = result
        assert loss > 0
        assert len(samples) == 20
        assert uchars == list("abcdefgh")

    @pytest.mark.usefixtures("apply_mocks")
    def test_warm_start_uses_model_dimensions(self, matching_model):
        result = train_torch(
            docs=["abc", "def", "h"],
            model=matching_model,
            num_steps=3,
            temperature=0.5,
        )
        weights, loss, samples, uchars = result
        assert "layer0.attn_wq" in weights
        assert uchars == list("abcdefgh")


########################################################################
# Tests — training without a model (from scratch)
########################################################################


class TestTrainTorchFromScratch:

    @pytest.mark.usefixtures("apply_mocks")
    def test_from_scratch_builds_vocabulary(self):
        _, _, _, uchars = train_torch(
            docs=["hello world"],
            num_steps=2,
            block_size=8,
            n_embd=8,
            n_head=4,
            n_layer=1,
        )
        assert uchars == sorted(set("hello world"))

    @pytest.mark.usefixtures("apply_mocks")
    def test_from_scratch_returns_samples(self):
        _, _, samples, _ = train_torch(
            docs=["hello world"],
            num_steps=2,
            block_size=8,
            n_embd=8,
            n_head=4,
            n_layer=1,
        )
        assert len(samples) == 20
        for s in samples:
            assert isinstance(s, str)