# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for local compute backends (LocalStdlibBackend, LocalTorchBackend)."""


from dataclasses import dataclass, field
from unittest.mock import ANY, MagicMock, patch

import pytest

from anvil.services.compute.compute_status import ComputeStatus
from anvil.services.compute.local_stdlib_backend import (
    LocalStdlibBackend,
    _load_weights_into_model,
)
from anvil.services.compute.local_torch_backend import LocalTorchBackend
from anvil.services.compute.result import ComputeResult


@pytest.fixture
def tiny_docs():
    return ["hello world", "goodbye moon", "the quick brown fox"]


@pytest.fixture
def tiny_config():
    return {
        "num_steps": 3,
        "n_embd": 8,
        "n_head": 4,
        "n_layer": 1,
        "block_size": 8,
        "learning_rate": 0.01,
        "beta1": 0.85,
        "beta2": 0.99,
        "temperature": 0.5,
    }


@pytest.fixture
def stdlib_backend():
    return LocalStdlibBackend()


@pytest.fixture
def torch_backend():
    return LocalTorchBackend()


class TestLocalStdlibBackend:
    async def test_run_returns_correct_result(
        self, stdlib_backend, tiny_docs, tiny_config
    ):
        """LocalStdlibBackend trains with stdlib engine and returns ComputeResult."""
        result = await stdlib_backend.run(
            tiny_docs,
            tiny_config,
            progress_callback=lambda s, l, **kwargs: None,
            stop_check=lambda: False,
        )

        assert isinstance(result, ComputeResult)
        assert result.status == ComputeStatus.COMPLETED
        assert result.model is not None
        assert result.final_loss is not None
        assert isinstance(result.final_loss, float)
        assert isinstance(result.samples, list)
        assert isinstance(result.uchars, list)
        assert result.engine == "stdlib"
        assert result.backend == "local"
        assert result.exported_remotely is False

    async def test_name_property(self, stdlib_backend):
        assert stdlib_backend.name == "local-stdlib"

    async def test_is_available(self, stdlib_backend):
        assert stdlib_backend.is_available() is True

    async def test_progress_callback_called(
        self, stdlib_backend, tiny_docs, tiny_config
    ):
        """progress_callback is invoked at least once during training."""
        calls: list[tuple[int, float]] = []

        def cb(step: int, loss: float, **kwargs: object) -> None:
            calls.append((step, loss))

        await stdlib_backend.run(
            tiny_docs,
            tiny_config,
            progress_callback=cb,
            stop_check=lambda: False,
        )

        assert len(calls) > 0
        assert calls[0][0] == 0  # first step
        assert isinstance(calls[0][1], float)

    async def test_stop_check_stops_early(self, stdlib_backend, tiny_docs, tiny_config):
        """stop_check returning True stops training before all steps complete."""
        stop_after = 1
        call_count = 0

        def cb(step: int, loss: float, **kwargs: object) -> None:
            nonlocal call_count
            call_count = step + 1

        def stop_check() -> bool:
            return call_count >= stop_after

        result = await stdlib_backend.run(
            tiny_docs,
            tiny_config,
            progress_callback=cb,
            stop_check=stop_check,
        )

        # Training stopped early (fewer than num_steps)
        assert call_count < tiny_config["num_steps"]
        assert result.status == ComputeStatus.COMPLETED
        assert result.model is not None

    async def test_stop_check_before_start(
        self, stdlib_backend, tiny_docs, tiny_config
    ):
        """If stop_check is True before any step, training returns zero-loss result."""

        def stop_check() -> bool:
            return True

        result = await stdlib_backend.run(
            tiny_docs,
            tiny_config,
            progress_callback=lambda s, l: None,
            stop_check=stop_check,
        )

        # train() initialises loss as Value(0.0) before the loop, so
        # returning immediately with zero steps produces a valid result.
        assert result.status == ComputeStatus.COMPLETED
        assert result.model is not None

    async def test_registered_in_registry(self):
        """LocalStdlibBackend is auto-registered in the compute registry."""
        from anvil.services.compute.registry import get_backend

        backend = get_backend("local-stdlib")
        assert isinstance(backend, LocalStdlibBackend)


class TestLocalTorchBackend:
    async def test_is_available_without_torch(self, torch_backend):
        """is_available() returns False when torch is not installed."""
        with patch(
            "anvil.services.compute.local_torch_backend._torch_available",
            return_value=False,
        ):
            assert torch_backend.is_available() is False

    async def test_is_available_with_torch(self, torch_backend):
        """is_available() returns True when torch is installed."""
        with patch(
            "anvil.services.compute.local_torch_backend._torch_available",
            return_value=True,
        ):
            assert torch_backend.is_available() is True

    async def test_name_property(self, torch_backend):
        assert torch_backend.name == "local-torch"

    async def test_run_with_mocked_torch(self, torch_backend, tiny_docs, tiny_config):
        """run() works with mocked train_torch, returning ComputeResult(engine='torch')."""
        fake_weights = {
            "wte": [[0.1, 0.2], [0.3, 0.4]],
            "lm_head": [[0.1, 0.2], [0.3, 0.4]],
        }
        fake_uchars = list("abcdefghij")

        with (
            patch(
                "anvil.services.compute.local_torch_backend.train_torch",
                return_value=(fake_weights, 0.42, ["sample1"], fake_uchars),
            ),
            patch(
                "anvil.services.compute.local_torch_backend._torch_available",
                return_value=True,
            ),
        ):
            result = await torch_backend.run(
                tiny_docs,
                {**tiny_config, "device": "cpu"},
                progress_callback=lambda s, l: None,
                stop_check=lambda: False,
            )

        assert isinstance(result, ComputeResult)
        assert result.status == ComputeStatus.COMPLETED
        assert result.model is not None
        assert result.final_loss == 0.42
        assert result.samples == ["sample1"]
        assert result.uchars == fake_uchars
        assert result.engine == "torch"
        assert result.backend == "local"

    async def test_progress_callback_called_with_torch(
        self, torch_backend, tiny_docs, tiny_config
    ):
        """progress_callback is invoked when using torch backend."""
        calls: list[tuple[int, float]] = []

        def _fake_train_torch(docs, device, num_steps=1000, **kw):
            progress_cb = kw.get("progress_callback")
            for s in range(min(num_steps, 3)):
                if progress_cb:
                    progress_cb(s, 0.1 * (s + 1))
            return ({"wte": [[0.1]]}, 0.5, ["s"], list("a"))

        with (
            patch(
                "anvil.services.compute.local_torch_backend.train_torch",
                side_effect=_fake_train_torch,
            ),
            patch(
                "anvil.services.compute.local_torch_backend._torch_available",
                return_value=True,
            ),
        ):
            await torch_backend.run(
                tiny_docs,
                {**tiny_config, "device": "cpu"},
                progress_callback=lambda s, l: calls.append((s, l)),
                stop_check=lambda: False,
            )

        assert len(calls) > 0

    async def test_stop_check_with_torch(self, torch_backend, tiny_docs, tiny_config):
        """stop_check stops torch training early."""
        call_count = 0

        def _fake_train_torch(docs, device, num_steps=1000, stop_check=None, **kw):
            nonlocal call_count
            progress_cb = kw.get("progress_callback")
            for s in range(min(num_steps, 5)):
                if stop_check and stop_check():
                    break
                if progress_cb:
                    progress_cb(s, 0.1)
                call_count = s + 1
            return ({"wte": [[0.1]]}, 0.5, ["s"], list("a"))

        with (
            patch(
                "anvil.services.compute.local_torch_backend.train_torch",
                side_effect=_fake_train_torch,
            ),
            patch(
                "anvil.services.compute.local_torch_backend._torch_available",
                return_value=True,
            ),
        ):
            result = await torch_backend.run(
                tiny_docs,
                {**tiny_config, "device": "cpu"},
                progress_callback=lambda s, l: None,
                stop_check=lambda: True,
            )

            assert result.status == ComputeStatus.COMPLETED

    async def test_registered_in_registry(self):
        """LocalTorchBackend is auto-registered in the compute registry."""
        from anvil.services.compute.registry import get_backend

        backend = get_backend("local-torch")
        assert isinstance(backend, LocalTorchBackend)


class TestLoadWeightsIntoModel:
    def test_loads_2d_matrix(self):
        from anvil.core.engine import LlamaModel

        model = LlamaModel(vocab_size=4, n_embd=4, n_head=2, n_layer=1, block_size=4)
        fake_weights = {
            "wte": [[0.5, 0.6, 0.7, 0.8], [0.9, 1.0, 1.1, 1.2]],
        }

        _load_weights_into_model(model, fake_weights)

        assert model.state_dict["wte"][0][0].data == 0.5
        assert model.state_dict["wte"][0][3].data == 0.8
        assert model.state_dict["wte"][1][2].data == 1.1

    def test_loads_1d_vector(self):
        from anvil.core.engine import LlamaModel

        model = LlamaModel(vocab_size=4, n_embd=4, n_head=2, n_layer=1, block_size=4)
        fake_weights = {
            "layer0.rms_1": [0.9, 1.1],
        }

        _load_weights_into_model(model, fake_weights)

        assert model.state_dict["layer0.rms_1"][0].data == 0.9
        assert model.state_dict["layer0.rms_1"][1].data == 1.1
