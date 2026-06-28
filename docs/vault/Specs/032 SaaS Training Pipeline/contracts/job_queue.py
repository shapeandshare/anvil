# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Job queue abstraction for asynchronous training job dispatch.

Encapsulates how training jobs are submitted for execution. Local mode
runs immediately in-process. SaaS mode dispatches to AWS Batch.
Supports four compute shapes: cpu, gpu, multi-gpu, multi-node.

Design contract artifact — targets Python 3.11+ (StrEnum, PEP 604 unions).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from enum import StrEnum
from typing import Any


class ComputeShape(StrEnum):
    """The four supported compute shapes."""

    CPU = "cpu"
    GPU = "gpu"
    MULTI_GPU = "multi-gpu"
    MULTI_NODE = "multi-node"


class JobStatus(StrEnum):
    """Status of a training job in the system."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ResourceSpec:
    """Structured compute requirements for a training job.

    Parameters
    ----------
    node_count : int
        Number of nodes (>1 = multi-node parallel Batch job).
    gpus_per_node : int
        GPUs per node (0 = CPU-only).
    vcpus : int
        Virtual CPUs per node.
    memory_mb : int
        Memory in MB per node.
    instance_class : str or None
        EC2 instance class override (e.g. ``"g5.xlarge"``).
    """

    def __init__(
        self,
        node_count: int = 1,
        gpus_per_node: int = 0,
        vcpus: int = 2,
        memory_mb: int = 4096,
        instance_class: str | None = None,
    ) -> None:
        self.node_count = node_count
        self.gpus_per_node = gpus_per_node
        self.vcpus = vcpus
        self.memory_mb = memory_mb
        self.instance_class = instance_class

    @property
    def compute_shape(self) -> ComputeShape:
        """Derive compute shape from resource spec."""
        if self.node_count > 1:
            return ComputeShape.MULTI_NODE
        if self.gpus_per_node > 1:
            return ComputeShape.MULTI_GPU
        if self.gpus_per_node == 1:
            return ComputeShape.GPU
        return ComputeShape.CPU


class TrainingJob:
    """A training job specification.

    Parameters
    ----------
    job_id : str
        Internal job ID.
    org_id : int
        Owner organization ID.
    created_by : int
        User ID of the submitter.
    config : dict
        Hyperparameter configuration.
    resource_spec : ResourceSpec
        Compute requirements.
    corpus_id : int or None
        Trained on this corpus.
    dataset_id : int or None
        Or this dataset.
    team_id : int or None
        Optional team scoping.
    """

    def __init__(
        self,
        job_id: str,
        org_id: int,
        created_by: int,
        config: dict[str, Any],
        resource_spec: ResourceSpec | None = None,
        corpus_id: int | None = None,
        dataset_id: int | None = None,
        team_id: int | None = None,
    ) -> None:
        self.job_id = job_id
        self.org_id = org_id
        self.created_by = created_by
        self.config = config
        self.resource_spec = resource_spec or ResourceSpec()
        self.corpus_id = corpus_id
        self.dataset_id = dataset_id
        self.team_id = team_id
        self.status: JobStatus = JobStatus.PENDING
        self.created_at: datetime = datetime.utcnow()
        self.started_at: datetime | None = None
        self.completed_at: datetime | None = None
        self.batch_job_id: str | None = None
        self.mlflow_run_id: str | None = None
        self.artifact_path: str | None = None
        self.error_message: str | None = None
        self.batch_log_stream: str | None = None
        self.final_loss: float | None = None


class Event:
    """A single job lifecycle event.

    Parameters
    ----------
    job_id : int
        The job this event belongs to.
    sequence : int
        Monotonic per-job sequence number.
    event_type : str
        One of ``submitted``, ``started``, ``metric``, ``checkpoint``,
        ``completed``, ``failed``, ``cancelled``.
    payload : dict
        Event-specific data (e.g. ``{step, loss}`` for metric events).
    ts : datetime or None
        Event timestamp.
    """

    def __init__(
        self,
        job_id: int,
        sequence: int,
        event_type: str,
        payload: dict[str, Any] | None = None,
        ts: datetime | None = None,
    ) -> None:
        self.job_id = job_id
        self.sequence = sequence
        self.event_type = event_type
        self.payload = payload or {}
        self.ts = ts or datetime.utcnow()


class JobQueue(ABC):
    """Abstract job submission and lifecycle tracking."""

    @abstractmethod
    async def submit(self, job: TrainingJob) -> str:
        """Submit a training job for execution.

        Returns the external (Batch) job ID.

        In SaaS mode, creates an AWS Batch job from the pre-registered
        job definition matching the compute shape (FR-045i).
        """

    @abstractmethod
    async def cancel(self, job_id: str) -> None:
        """Cancel a pending or running job.

        Idempotent — safe to call on already-terminal jobs (FR-045n).
        """

    @abstractmethod
    async def status(self, job_id: str) -> JobStatus:
        """Query the current external status of a job."""


# Implementations:
# - InProcessJobQueue: immediately runs via asyncio.create_task (in anvil/storage/)
# - BatchJobQueue: wraps boto3 batch.submit_job (in anvil/_saas/implementations/)
