"""Unified result value object for compute backends.

The key design seam: local backends return a model object in-process;
remote backends produce artifacts in cloud/S3. ``ComputeResult``
normalises both paths into a single typed value.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ComputeStatus(str, Enum):
    """Lifecycle status of a compute run."""

    SUBMITTED = "submitted"  # remote: job accepted, not yet running
    RUNNING = "running"  # remote: job in progress
    COMPLETED = "completed"  # finished successfully
    FAILED = "failed"  # finished with error


@dataclass
class ComputeResult:
    """Normalised result of a training run, regardless of where it executed.

    Local path (``model is not None``)
        ``on_complete`` runs local safetensors export + MLflow ``log_artifact``.

    Remote path (``exported_remotely is True``)
        MLflow logging happened inside the remote job already.
        ``on_complete`` does metadata-only ``register_model(runs:/…)``,
        skipping local export entirely.
    """

    status: ComputeStatus

    # -- local path (in-process model) --
    model: object | None = None  # anvil.core.engine.LlamaModel | None (avoid cycle)
    final_loss: float | None = None
    samples: list[str] = field(default_factory=list)
    uchars: list[str] = field(default_factory=list)

    # -- remote path (artifact references) --
    exported_remotely: bool = False
    artifact_uris: dict[str, str] = field(default_factory=dict)
    remote_job_id: str | None = None
    remote_mlflow_run_id: str | None = None

    # -- both paths --
    error_message: str | None = None

    # provenance
    engine: str = "stdlib"  # stdlib | torch
    backend: str = "local"  # local | modal | …
