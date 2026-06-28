# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""PyTorch local compute backend.

Wraps ``anvil.services.training.torch_engine.train_torch`` as an async
``ComputeBackendProtocol`` implementation using
``loop.run_in_executor()`` so it integrates with the async training
service without blocking the event loop.

Auto-registers as ``"local-torch"`` in the compute registry at module
import time.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from ...core.engine import LlamaModel
from ..training.torch_engine import TorchLlamaModel
from ..training.torch_engine import load_torch_weights_from_lists
from ..training.torch_engine import torch_available as _torch_available
from ..training.torch_engine import train_torch
from .compute_backend_result import ComputeBackendResult
from .compute_status import ComputeStatus
from .local_stdlib_backend import _load_weights_into_model
from .protocol import ProgressCallback, StopCheck
from .registry import register
from .registry_backend import RegistryBackend
from .result import ComputeResult
from .training_engine import TrainingEngine


class LocalTorchBackend:
    """Wraps ``anvil.core.torch_engine.train_torch`` as an async compute backend.

    Runs the PyTorch training loop in a thread pool executor.

    Returns a CPU ``LlamaModel`` (weights loaded from the torch run's
    exported state dict) so downstream code (safetensors export, etc.)
    always works with the same model type regardless of which engine
    was used for training.

    Automatically registered as ``"local-torch"`` in the compute registry
    at module import time.
    """

    #: Backend identifier used by the registry and resolution layer.
    name = RegistryBackend.LOCAL_TORCH

    @staticmethod
    def is_available() -> bool:
        """Check whether the PyTorch backend is available.

        Returns ``True`` only if PyTorch is installed and importable
        in the current environment.

        Returns
        -------
        bool
            ``True`` if ``torch`` can be imported.
        """
        return _torch_available()

    async def run(
        self,
        docs: list[str],
        config: dict[str, Any],
        *,
        progress_callback: ProgressCallback,
        stop_check: StopCheck,
    ) -> ComputeResult:
        """Run training using the PyTorch engine in a thread pool.

        Delegates to ``anvil.core.torch_engine.train_torch`` via
        ``loop.run_in_executor()``.  GPU-trained weights are wrapped
        into a CPU ``LlamaModel`` for downstream compatibility.

        Parameters
        ----------
        docs : list[str]
            Training documents (raw text strings).
        config : dict[str, Any]
            Hyperparameter dictionary (``num_steps``, ``n_embd``,
            ``n_head``, ``n_layer``, ``block_size``, ``learning_rate``,
            ``beta1``, ``beta2``, ``temperature``, ``device``).
        progress_callback : ProgressCallback
            Callable invoked periodically with ``(step, loss)``.
        stop_check : StopCheck
            Callable returning ``True`` if cancellation was requested.

        Returns
        -------
        ComputeResult
            Completed or failed result with in-process model data.

        Raises
        ------
        StopRequested
            Re-raised if the stop check triggered during training.
        """
        loop = asyncio.get_event_loop()
        device = config.get("device", "cpu")

        # ── warm-start: resolve base model checkpoint ──────────────────
        base_model_ref = config.get("base_model_ref")
        train_model: TorchLlamaModel | None = None

        if base_model_ref is not None:
            checkpoint_path = Path(
                f"data/models/experiment_{base_model_ref}.json"
            )
            base_model = LlamaModel.load(str(checkpoint_path))
            if base_model.chars is None:
                msg = (
                    f"Base model experiment_{base_model_ref}.json "
                    f"has no character vocabulary"
                )
                raise ValueError(msg)
            train_model = TorchLlamaModel(
                vocab_size=base_model.vocab_size,
                n_embd=base_model.n_embd,
                n_head=base_model.n_head,
                n_layer=base_model.n_layer,
                block_size=base_model.block_size,
            )
            # Transfer the base model's trained weights into the torch model
            # so training genuinely continues (FR-002 parity), rather than
            # restarting from random init. The checkpoint stores weights as
            # plain float lists under "state_dict".
            with checkpoint_path.open(encoding="utf-8") as f:
                checkpoint = json.load(f)
            load_torch_weights_from_lists(train_model, checkpoint["state_dict"])
            train_model.chars = list(base_model.chars)  # type: ignore[attr-defined]

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
                    model=train_model,
                ),
            )

            # Wrap GPU weights into a CPU LlamaModel for downstream compatibility
            if train_model is not None:
                model = LlamaModel(
                    vocab_size=train_model.vocab_size,
                    n_embd=train_model.n_embd,
                    n_head=train_model.n_head,
                    n_layer=train_model.n_layer,
                    block_size=train_model.block_size,
                )
            else:
                model = LlamaModel(
                    vocab_size=len(uchars) + 1,
                    n_embd=config.get("n_embd", 16),
                    n_head=config.get("n_head", 4),
                    n_layer=config.get("n_layer", 1),
                    block_size=config.get("block_size", 16),
                )
            _load_weights_into_model(model, raw_weights)

        except Exception as exc:
            if type(exc).__name__ in ("StopRequested", "DivergenceError"):
                raise
            return ComputeResult(
                status=ComputeStatus.FAILED,
                error_message=str(exc),
                engine=TrainingEngine.TORCH,
                backend=ComputeBackendResult.LOCAL,
            )

        return ComputeResult(
            status=ComputeStatus.COMPLETED,
            model=model,
            final_loss=final_loss,
            samples=samples,
            uchars=uchars,
            engine=TrainingEngine.TORCH,
            backend=ComputeBackendResult.LOCAL,
        )


# ── auto-register ──────────────────────────────────────────────────────


def _torch_factory() -> LocalTorchBackend:
    """Factory callable for the PyTorch local backend.

    Returns
    -------
    LocalTorchBackend
        A new instance of the PyTorch training backend.
    """
    return LocalTorchBackend()


register(RegistryBackend.LOCAL_TORCH, _torch_factory)  # type: ignore[arg-type]
