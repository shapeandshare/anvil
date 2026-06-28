# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Compute backend abstraction for training execution.

Extends the existing ``ComputeBackend`` pattern from
``anvil/services/compute/`` to support Batch dispatch.
Implements the three-plane orchestration model (AD-11):
control plane admits/configures, scheduler (Batch) queues/scales,
executor (compute pod) runs training.
"""

from abc import ABC, abstractmethod
from typing import Any

from .event_bus import EventBus
from .job_queue import ResourceSpec, TrainingJob


class ComputeBackend(ABC):
    """Abstract training execution backend.

    SaaS mode dispatches to AWS Batch (three-plane model, never polls
    the pod — FR-045g). Local mode runs in-process.
    """

    @abstractmethod
    async def run(
        self,
        job: TrainingJob,
        event_bus: EventBus,
    ) -> dict[str, Any]:
        """Execute a training job.

        Parameters
        ----------
        job : TrainingJob
            The job to execute.
        event_bus : EventBus
            Channel for publishing live step metrics.

        Returns
        -------
        dict
            Result with keys: ``final_loss``, ``samples``, ``model``,
            ``artifact_path``, ``error``.
        """

    @abstractmethod
    async def submit(self, spec: ResourceSpec, job_id: str) -> str:
        """Submit a job to the compute backend.

        In SaaS mode, dispatches to Batch with the given ResourceSpec.
        Returns the external execution ID.

        Parameters
        ----------
        spec : ResourceSpec
            Compute requirements (node_count, gpus_per_node, etc.).
        job_id : str
            The application-level job ID.

        Returns
        -------
        str
            External execution (Batch) ID.
        """

    @abstractmethod
    async def cancel(self, execution_id: str) -> None:
        """Cancel a running execution.

        Parameters
        ----------
        execution_id : str
            The external execution ID to cancel.
        """


# Implementations (existing, in anvil/services/compute/):
# - LocalStdlibBackend: in-process, same thread
# - LocalTorchBackend: in-process, thread pool

# New implementation (in anvil/_saas/implementations/):
# - BatchComputeBackend: wraps BatchJobQueue.submit() — three-plane,
#   never polls pod (FR-045g)
