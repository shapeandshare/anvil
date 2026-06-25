# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Protocol definitions for compute backends.

Defines the structural typing contract (PEP 544) that every compute backend
must satisfy, along with callback type aliases used during training progress
reporting and cancellation checking.

Compute backends do not inherit from an ABC; any class with a ``name``
attribute, an ``is_available()`` static method, and an ``async def run()``
method satisfies ``ComputeBackendProtocol`` structurally.
"""

from collections.abc import Callable
from typing import Any, Protocol

from .result import ComputeResult

ProgressCallback = Callable[..., None]
#: Callback invoked with ``(step, loss)`` and optional keyword-only signals
#: (``tokens``, ``grad_norm``) to report training progress. A ``step`` value
#: of ``-1`` signals that a remote job has been submitted.

StopCheck = Callable[[], bool]
#: Callback invoked periodically; returns ``True`` if the caller has
#: requested cancellation, ``False`` to continue training.


class ComputeBackendProtocol(Protocol):
    """Structural type for compute backends (PEP 544 -- not an ABC).

    Any plain class with ``name: str``, ``is_available()``, and
    ``run(...)`` satisfies this protocol. No inheritance required.

    Implementations are expected to auto-register in the compute registry
    at module import time via ``register()``.
    """

    name: str
    """Human-readable identifier for this backend (e.g. ``"local-stdlib"``)."""

    def is_available(self) -> bool:
        """Check whether this backend can be used in the current environment.

        Returns
        -------
        bool
            ``True`` if the backend's dependencies are installed and the
            runtime environment is capable of running jobs.
        """

    async def run(
        self,
        docs: list[str],
        config: dict[str, Any],
        *,
        progress_callback: ProgressCallback,
        stop_check: StopCheck,
    ) -> ComputeResult:
        """Execute a training run on this backend.

        Parameters
        ----------
        docs : list[str]
            Training documents (raw text strings).
        config : dict
            Flat dictionary of hyperparameters and configuration keys
            (e.g. ``num_steps``, ``n_embd``, ``learning_rate``).
        progress_callback : ProgressCallback
            Callable invoked periodically with ``(step, loss)`` to report
            training progress.
        stop_check : StopCheck
            Callable invoked periodically; returns ``True`` if the caller
            has requested cancellation.

        Returns
        -------
        ComputeResult
            Normalised result containing either trained model data (local
            path) or artifact URIs (remote path).
        """
