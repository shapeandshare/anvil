"""Compute backend abstraction for training execution.

Extends the existing ``ComputeBackend`` pattern from
``anvil/services/compute/`` to support Batch dispatch.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable

from .event_bus import EventBus
from .job_queue import TrainingJob


class ComputeBackend(ABC):
    """Abstract training execution backend."""

    @abstractmethod
    async def run(
        self,
        job: TrainingJob,
        event_bus: EventBus,
        progress_callback: Callable[[int, float], None] | None = None,
    ) -> dict[str, Any]:
        """Execute a training job.

        Parameters
        ----------
        job : TrainingJob
            The job to execute.
        event_bus : EventBus
            Channel for publishing live step metrics.
        progress_callback : callable, optional
            Synchronous callback for per-step progress (used in local mode
            for direct queue injection).

        Returns
        -------
        dict
            Result with keys: ``final_loss``, ``samples``, ``model``,
            ``artifact_path``, ``error``.
        """


# Implementations (existing, in anvil/services/compute/):
# - LocalStdlibBackend: in-process, same thread
# - LocalTorchBackend: in-process, thread pool
# - ModalBackend: remote Modal cloud GPU

# New implementation (in anvil/_saas/implementations/):
# - BatchComputeBackend: wraps JobQueue.submit() — no local execution
