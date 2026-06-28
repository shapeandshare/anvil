# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Stdlib-only local compute backend.

Wraps ``anvil.core.engine.train`` as an async ``ComputeBackendProtocol``
implementation using ``loop.run_in_executor()`` so it integrates with the
async training service without blocking the event loop.

Auto-registers as ``"local-stdlib"`` in the compute registry at module
import time.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from ...core.engine import LlamaModel, train
from .compute_backend_result import ComputeBackendResult
from .compute_status import ComputeStatus
from .protocol import ProgressCallback, StopCheck
from .registry import register
from .registry_backend import RegistryBackend
from .result import ComputeResult
from .training_engine import TrainingEngine


def _load_weights_into_model(model: LlamaModel, weights: dict[str, Any]) -> None:
    """Load exported weight lists into a CPU LlamaModel.

    Handles both 2D matrices (attention, SwiGLU, embeddings) and
    1D vectors (RMSNorm learned scale parameters) by iterating over
    the weight dictionary and copying values element-by-element into
    the model's state dict.

    Parameters
    ----------
    model : LlamaModel
        Target model to load weights into.  Must be initialised with
        the correct architecture dimensions.
    weights : dict
        Dictionary mapping layer names to weight data.  Values are
        either nested lists (2D matrices) or flat lists (1D vectors).
    """
    for k, data in weights.items():
        mat = model.state_dict[k]
        assert isinstance(mat, list), f"Expected a list, got {type(mat)}"
        if mat and isinstance(mat[0], list):
            # 2D matrix
            for i, row in enumerate(data):
                for j, val in enumerate(row):
                    mat[i][j].data = val  # type: ignore[index]
        else:
            # 1D vector (RMSNorm scales)
            for i, val in enumerate(data):
                mat[i].data = val  # type: ignore[union-attr]


class LocalStdlibBackend:
    """Wraps ``anvil.core.engine.train`` as an async compute backend.

    Runs the stdlib-only training loop in a thread pool executor so the
    async event loop is never blocked.

    Automatically registered as ``"local-stdlib"`` in the compute registry
    at module import time.
    """

    #: Backend identifier used by the registry and resolution layer.
    name = RegistryBackend.LOCAL_STDLIB

    @staticmethod
    def is_available() -> bool:
        """Check whether the stdlib backend is available in this environment.

        The stdlib backend has no external dependencies, so it is always
        available.

        Returns
        -------
        bool
            Always ``True``.
        """
        return True

    async def run(
        self,
        docs: list[str],
        config: dict[str, Any],
        *,
        progress_callback: ProgressCallback,
        stop_check: StopCheck,
    ) -> ComputeResult:
        """Run training using the stdlib-only engine in a thread pool.

        Delegates to ``anvil.core.engine.train`` via
        ``loop.run_in_executor()`` to avoid blocking the async event loop.

        Parameters
        ----------
        docs : list[str]
            Training documents (raw text strings).
        config : dict[str, Any]
            Hyperparameter dictionary (``num_steps``, ``n_embd``,
            ``n_head``, ``n_layer``, ``block_size``, ``learning_rate``,
            ``beta1``, ``beta2``, ``temperature``).
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

        base_model_ref = config.get("base_model_ref")
        loaded_model: LlamaModel | None = None
        if base_model_ref is not None:
            model_path = Path(f"data/models/experiment_{base_model_ref}.json")
            if not model_path.exists():
                raise RuntimeError(
                    f"Base model checkpoint not found: {model_path}. "
                    f"Experiment {base_model_ref} may not have been "
                    f"trained or exported."
                )
            loaded_model = LlamaModel.load(str(model_path))

        try:
            model, final_loss, samples, uchars = await loop.run_in_executor(
                None,
                lambda: train(
                    docs,
                    model=loaded_model,
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
            if type(exc).__name__ in ("StopRequested", "DivergenceError"):
                raise
            return ComputeResult(
                status=ComputeStatus.FAILED,
                error_message=str(exc),
                engine=TrainingEngine.STDLIB,
                backend=ComputeBackendResult.LOCAL,
            )

        return ComputeResult(
            status=ComputeStatus.COMPLETED,
            model=model,
            final_loss=final_loss,
            samples=samples,
            uchars=uchars,
            engine=TrainingEngine.STDLIB,
            backend=ComputeBackendResult.LOCAL,
        )


# ── auto-register ──────────────────────────────────────────────────────


def _local_factory() -> LocalStdlibBackend:
    """Factory callable for the stdlib local backend.

    Returns
    -------
    LocalStdlibBackend
        A new instance of the stdlib training backend.
    """
    return LocalStdlibBackend()


register(RegistryBackend.LOCAL_STDLIB, _local_factory)  # type: ignore[arg-type]
