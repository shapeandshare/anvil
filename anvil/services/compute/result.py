"""Unified result value object for compute backends.

The key design seam: local backends return a model object in-process;
remote backends produce artifacts in cloud/S3. ``ComputeResult``
normalises both paths into a single typed value.
"""

from pydantic import BaseModel, Field

from .compute_backend_result import ComputeBackendResult
from .compute_status import ComputeStatus
from .training_engine import TrainingEngine


class ComputeResult(BaseModel):
    """Normalised result of a training run, regardless of where it executed.

    The model supports two mutually exclusive paths:

    **Local path** (``model is not None``)
        ``on_complete`` runs local safetensors export + MLflow
        ``log_artifact`` using the in-process model object.

    **Remote path** (``exported_remotely is True``)
        MLflow logging happened inside the remote job already.
        ``on_complete`` does metadata-only ``register_model(runs:/...)``,
        skipping local export entirely.

    Parameters
    ----------
    status : ComputeStatus
        Final lifecycle status of the compute run.
    model : object | None
        In-process ``LlamaModel`` instance, or ``None`` for remote runs.
    final_loss : float | None
        Final training loss value, or ``None`` on failure.
    samples : list[str]
        Text samples generated during training for qualitative inspection.
    uchars : list[str]
        Unique characters discovered in the training corpus (vocabulary).
    exported_remotely : bool
        ``True`` if artifact export was handled by the remote backend.
    artifact_uris : dict[str, str]
        Mapping of artifact names to URIs (e.g. ``{"mlflow_run_id": "..."}``).
    remote_job_id : str | None
        Backend-specific identifier for the remote job, if applicable.
    remote_mlflow_run_id : str | None
        MLflow run ID assigned by the remote job's own tracking, if
        applicable.
    error_message : str | None
        Human-readable error description, or ``None`` on success.
    engine : TrainingEngine
        Training engine used for the run.
    backend : ComputeBackendResult
        Compute backend that executed the run.
    """

    status: ComputeStatus

    # -- local path (in-process model) --
    # ``anvil.core.engine.LlamaModel`` instance, or ``None`` for remote runs.
    # Type is ``object`` to avoid circular imports.
    model: object | None = None

    # Final training loss value, or ``None`` if the run failed.
    final_loss: float | None = None

    # Text samples generated during training for qualitative inspection.
    samples: list[str] = Field(default_factory=list)

    # Unique characters discovered in the training corpus (vocabulary).
    uchars: list[str] = Field(default_factory=list)

    # -- remote path (artifact references) --
    # ``True`` if artifact export was handled by the remote backend.
    exported_remotely: bool = False

    # Mapping of artifact names to URIs (e.g. ``{"mlflow_run_id": "..."}``).
    artifact_uris: dict[str, str] = Field(default_factory=dict)

    # Backend-specific identifier for the remote job, if applicable.
    remote_job_id: str | None = None

    # MLflow run ID assigned by the remote job's own tracking.
    remote_mlflow_run_id: str | None = None

    # -- both paths --
    # Human-readable error description, or ``None`` on success.
    error_message: str | None = None

    # provenance
    # Training engine used for the run.
    engine: TrainingEngine = TrainingEngine.STDLIB

    # Compute backend that executed the run.
    backend: ComputeBackendResult = ComputeBackendResult.LOCAL
