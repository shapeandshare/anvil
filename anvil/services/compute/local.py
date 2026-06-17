"""Local compute backends (stdlib and torch).

Wraps ``anvil.core.engine.train`` and ``anvil.core.torch_engine.train_torch``
as async ``ComputeBackendProtocol`` implementations.

Both use ``loop.run_in_executor()`` so they integrate with the async
training service without blocking the event loop.

Both auto-register in the compute registry at module import time.
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable

from anvil.core.engine import LlamaModel, train
from anvil.core.torch_engine import torch_available as _torch_available
from anvil.core.torch_engine import train_torch
from anvil.services.compute.protocol import ComputeBackendProtocol, ProgressCallback, StopCheck
from anvil.services.compute.registry import register
from anvil.services.compute.result import ComputeResult, ComputeStatus


def _load_weights_into_model(model: LlamaModel, weights: dict) -> None:
    """Load exported weight lists into a CPU LlamaModel.

    Handles both 2D matrices (attention, SwiGLU, embeddings) and
    1D vectors (RMSNorm learned scale parameters).
    """
    for k, data in weights.items():
        mat = model.state_dict[k]
        if isinstance(mat[0], list):
            # 2D matrix
            for i, row in enumerate(data):
                for j, val in enumerate(row):
                    mat[i][j].data = val
        else:
            # 1D vector (RMSNorm scales)
            for i, val in enumerate(data):
                mat[i].data = val


class LocalStdlibBackend:
    """Wraps ``anvil.core.engine.train`` as an async compute backend.

    Runs the stdlib-only training loop in a thread pool executor so the
    async event loop is never blocked.
    """

    name = "local-stdlib"

    @staticmethod
    def is_available() -> bool:
        return True

    async def run(
        self,
        docs: list[str],
        config: dict[str, Any],
        *,
        progress_callback: ProgressCallback,
        stop_check: StopCheck,
    ) -> ComputeResult:
        loop = asyncio.get_event_loop()

        try:
            model, final_loss, samples, uchars = await loop.run_in_executor(
                None,
                lambda: train(
                    docs,
                    num_steps=config.get("num_steps", 1000),
                    n_embd=config.get("n_embd", 16),
                    n_head=config.get("n_head", 4),
                    n_layer=config.get("n_layer", 1),
                    block_size=config.get("block_size", 16),
                    learning_rate=config.get("learning_rate", 0.01),
                    beta1=config.get("beta1", 0.85),
                    beta2=config.get("beta2", 0.99),
                    temperature=config.get("temperature", 0.5),
                    progress_callback=progress_callback,
                    optimizer_state_callback=None,
                    stop_check=stop_check,
                ),
            )
        except Exception as exc:
            if type(exc).__name__ == "StopRequested":
                raise
            return ComputeResult(
                status=ComputeStatus.FAILED,
                error_message=str(exc),
                engine="stdlib",
                backend="local",
            )

        return ComputeResult(
            status=ComputeStatus.COMPLETED,
            model=model,
            final_loss=final_loss,
            samples=samples,
            uchars=uchars,
            engine="stdlib",
            backend="local",
        )


class LocalTorchBackend:
    """Wraps ``anvil.core.torch_engine.train_torch`` as an async compute backend.

    Runs the PyTorch training loop in a thread pool executor.

    Returns a CPU ``LlamaModel`` (weights loaded from the torch run's
    exported state dict) so downstream code (safetensors export, etc.)
    always works with the same model type regardless of which engine
    was used for training.
    """

    name = "local-torch"

    @staticmethod
    def is_available() -> bool:
        return _torch_available()

    async def run(
        self,
        docs: list[str],
        config: dict[str, Any],
        *,
        progress_callback: ProgressCallback,
        stop_check: StopCheck,
    ) -> ComputeResult:
        loop = asyncio.get_event_loop()
        device = config.get("device", "cpu")

        try:
            raw_weights, final_loss, samples, uchars = await loop.run_in_executor(
                None,
                lambda: train_torch(
                    docs,
                    device=device,
                    num_steps=config.get("num_steps", 1000),
                    n_embd=config.get("n_embd", 16),
                    n_head=config.get("n_head", 4),
                    n_layer=config.get("n_layer", 1),
                    block_size=config.get("block_size", 16),
                    learning_rate=config.get("learning_rate", 0.01),
                    beta1=config.get("beta1", 0.85),
                    beta2=config.get("beta2", 0.99),
                    temperature=config.get("temperature", 0.5),
                    progress_callback=progress_callback,
                    stop_check=stop_check,
                ),
            )

            # Wrap GPU weights into a CPU LlamaModel for downstream compatibility
            model = LlamaModel(
                vocab_size=len(uchars) + 1,
                n_embd=config.get("n_embd", 16),
                n_head=config.get("n_head", 4),
                n_layer=config.get("n_layer", 1),
                block_size=config.get("block_size", 16),
            )
            _load_weights_into_model(model, raw_weights)

        except Exception as exc:
            if type(exc).__name__ == "StopRequested":
                raise
            return ComputeResult(
                status=ComputeStatus.FAILED,
                error_message=str(exc),
                engine="torch",
                backend="local",
            )

        return ComputeResult(
            status=ComputeStatus.COMPLETED,
            model=model,
            final_loss=final_loss,
            samples=samples,
            uchars=uchars,
            engine="torch",
            backend="local",
        )


# ── auto-register ──────────────────────────────────────────────────────

def _local_factory() -> LocalStdlibBackend:
    return LocalStdlibBackend()


def _torch_factory() -> LocalTorchBackend:
    return LocalTorchBackend()


register("local-stdlib", _local_factory)
register("local-torch", _torch_factory)
