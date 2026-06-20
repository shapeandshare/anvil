"""Job queue abstraction for asynchronous training job dispatch.

Encapsulates how training jobs are submitted for execution. Local mode
runs immediately in-process. SaaS mode dispatches to AWS Batch.

Note: design contract artifact — targets Python 3.11+ (StrEnum, PEP 604 unions).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class JobStatus(StrEnum):
    """Status of a training job in the system."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TrainingJob:
    """A training job specification."""

    job_id: str
    user_id: int
    config: dict[str, Any]
    corpus_id: int | None = None
    dataset_id: int | None = None
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    artifact_path: str | None = None
    mlflow_run_id: str | None = None
    batch_job_id: str | None = None


class JobQueue(ABC):
    """Abstract job submission and lifecycle tracking."""

    @abstractmethod
    async def submit(self, job: TrainingJob) -> str:
        """Submit a training job for execution. Returns the external job ID."""

    @abstractmethod
    async def cancel(self, job_id: str) -> None:
        """Cancel a pending or running job."""

    @abstractmethod
    async def status(self, job_id: str) -> JobStatus:
        """Query the current status of a job."""

    @abstractmethod
    async def list_active(self, user_id: int) -> list[TrainingJob]:
        """List all active (pending or running) jobs for a user."""


# Implementations:
# - InProcessJobQueue: immediately runs via asyncio.create_task (new, in anvil/storage/)
# - BatchJobQueue: wraps boto3 batch.submit_job (new, in anvil/_saas/implementations/)
