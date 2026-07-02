# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""MLflow experiment tracking service — run lifecycle, metrics, artifacts, registry.

Provides the ``TrackingService`` class for managing MLflow experiment runs,
logging metrics and parameters, managing datasets and model registry,
and recording dataset/corpus lifecycle events.

The service uses a typed ``DegradedState`` state machine instead of a raw
boolean for degraded mode.  Known MLflow/transport exceptions enter
degraded mode; unexpected exceptions (``TypeError``, ``AttributeError``)
propagate to the caller.  Automatic reconnection with exponential backoff
is attempted for transient failures (``DegradedReason.UNREACHABLE``).
"""

# pylint: disable=broad-exception-caught

import asyncio
import logging
import random
import threading
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any

import mlflow
import mlflow.entities
from mlflow.exceptions import MlflowException
from mlflow.tracking import MlflowClient
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import get_config
from ...db.session import AsyncSessionLocal
from .._shared.capability_unavailable import CapabilityUnavailable
from .._shared.evaluation_status import EvaluationRunStatus
from .degraded_reason import DegradedReason
from .degraded_state import DegradedState
from .mlflow_capabilities import TrackingCapabilities, detect_capabilities
from .mlflow_inputs import MlflowInputResolver
from .tracking_status import TrackingStatus

try:
    from mlflow.genai.datasets import create_dataset, get_dataset
except ImportError:
    create_dataset = None
    get_dataset = None

logger = logging.getLogger(__name__)

_system_metrics_enabled = False
_MlflowClientLike = Any

# MLflow tag key constants
TAG_ENTITY_TYPE = "anvil.entity_type"
TAG_ENTITY_ID = "anvil.entity_id"
TAG_EVENT = "anvil.event"

# Known transient/operational exceptions that should enter degraded mode.
# These cover MLflow API errors, HTTP transport failures, and stdlib
# connection/timeout errors.  Everything else (TypeError, AttributeError,
# ValueError from bad caller args) must propagate.
_TRANSIENT_EXCEPTIONS = (
    MlflowException,
    ConnectionError,
    TimeoutError,
    OSError,
)

_BACKOFF_INITIAL = 1.0
"""float: Initial backoff delay in seconds for reconnection retries."""
_BACKOFF_MULTIPLIER = 2.0
"""float: Multiplier applied to the backoff delay after each retry."""
_BACKOFF_MAX = 30.0
"""float: Maximum backoff delay in seconds."""
_BACKOFF_JITTER = 0.25
"""float: Fraction of the current delay used as jitter ( ±25% )."""


class TrackingService:
    """Manages MLflow experiment tracking: runs, metrics, artifacts, and registry.

    Wraps ``mlflow.tracking.MlflowClient`` with async-friendly methods
    and a ``DegradedState`` state machine that gracefully degrades when
    MLflow is unavailable and recovers automatically from transient
    failures.  See ``tracking_status.py`` for the state machine model.
    """

    def __init__(
        self,
        *,
        tracking_uri: str | None = None,
        experiment_name: str = "anvil",
        client_factory: Callable[[str], _MlflowClientLike] | None = None,
    ):
        """Initialise the tracking service.

        Parameters
        ----------
        tracking_uri : str, optional
            MLflow tracking server URI. Defaults to the configured
            ``mlflow_uri`` from app config.
        experiment_name : str
            MLflow experiment name. Defaults to ``"anvil"``.
        client_factory : callable, optional
            Factory for creating ``MlflowClient`` instances. Defaults
            to ``mlflow.tracking.MlflowClient``.
        """
        cfg = get_config()
        self._tracking_uri = tracking_uri or cfg["mlflow_uri"]
        self._experiment_name = experiment_name
        self._state: DegradedState = DegradedState.active()

        if client_factory is not None:
            self._client_factory: Callable[[str], _MlflowClientLike] = client_factory
        else:
            self._client_factory = MlflowClient

        self._client: _MlflowClientLike | None = None
        self._experiment_id: str | None = None
        self._lock: asyncio.Lock = asyncio.Lock()
        self._thread_lock: threading.Lock = threading.Lock()

    ########################################################################
    # Public accessors
    ########################################################################

    @property
    def is_degraded(self) -> bool:
        """Whether the service is in degraded mode (MLflow unavailable)."""
        return self._state.status == "degraded"

    @property
    def tracking_status(self) -> TrackingStatus:
        """Return the current tracking status for the health endpoint.

        Returns
        -------
        TrackingStatus
            Pydantic model with ``status``, ``reason``, ``message``,
            and ``last_attempt``.
        """
        return TrackingStatus(
            status=self._state.status,
            reason=self._state.reason,
            message=self._state.message,
            last_attempt=self._state.last_attempt,
        )

    ########################################################################
    # Lazy initialisation
    ########################################################################

    def _classify_exception(self, exc: BaseException) -> tuple[DegradedReason, str]:
        """Classify an exception into a ``DegradedReason`` and human-readable
        message.

        Parameters
        ----------
        exc : BaseException
            The exception to classify.

        Returns
        -------
        tuple[DegradedReason, str]
            The reason and a human-readable message.
        """
        if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
            return DegradedReason.UNREACHABLE, (
                f"MLflow server at {self._tracking_uri} is unreachable: {exc}"
            )
        if isinstance(exc, MlflowException):
            code = getattr(exc, "error_code", None)
            if code in ("UNAUTHENTICATED", "PERMISSION_DENIED"):
                return DegradedReason.AUTH_FAILURE, (
                    f"MLflow authentication failed (HTTP {code}): {exc}"
                )
            if code in ("BAD_REQUEST", "INVALID_PARAMETER_VALUE"):
                return DegradedReason.INCOMPATIBLE_VERSION, (
                    f"MLflow request rejected (HTTP {code}): {exc}"
                )
            return DegradedReason.PERMANENT_ERROR, (f"MLflow error: {exc}")
        return DegradedReason.UNKNOWN, (f"Unexpected tracking error: {exc}")

    def _maybe_reconnect_sync(self) -> bool:
        """Attempt to reconnect to MLflow synchronously (runs in executor).

        Applies exponential backoff with jitter.  Only retries when the
        degraded reason is ``UNREACHABLE``.  State mutations are protected
        by a ``threading.Lock`` since this runs in the executor thread pool.

        Returns
        -------
        bool
            ``True`` if reconnected successfully, ``False`` otherwise.
        """
        # Fast path: already active (check without lock for performance).
        if self._state.status == "active":
            return True
        if not self._state.reason or not self._state.reason.should_retry:
            return False

        with self._thread_lock:
            # Double-check after acquiring lock — another thread may
            # have recovered while we were waiting.  mypy flags this
            # as a non-overlapping check in the single-threaded view,
            # but it is deliberate in the concurrent view.
            if self._state.status == "active":  # type: ignore[comparison-overlap]
                return True

            delay = min(
                _BACKOFF_INITIAL * (_BACKOFF_MULTIPLIER**self._state.retry_count),
                _BACKOFF_MAX,
            )
            jitter = delay * random.uniform(-_BACKOFF_JITTER, _BACKOFF_JITTER)
            time.sleep(max(0.0, delay + jitter))

            try:
                client = self._client_factory(self._tracking_uri)
                exp = client.get_experiment_by_name(self._experiment_name)
                if exp:
                    self._experiment_id = exp.experiment_id
                else:
                    self._experiment_id = client.create_experiment(
                        self._experiment_name
                    )
                self._client = client
                self._state = DegradedState.active()
                logger.warning(
                    "Tracking service recovered — MLflow reconnected to %s",
                    self._tracking_uri,
                )
                return True
            except _TRANSIENT_EXCEPTIONS as exc:
                self._state.retry_count += 1
                self._state.last_attempt = time.time()
                reason, msg = self._classify_exception(exc)
                self._state.reason = reason
                self._state.message = msg
                logger.warning(
                    "Tracking service still degraded (attempt %d): %s",
                    self._state.retry_count,
                    msg,
                )
                return False

    def _lazy_init(self) -> _MlflowClientLike:
        """Lazily initialise the MLflow client and experiment.

        If the service is degraded, attempts automatic reconnection
        via ``_maybe_reconnect_sync`` before returning the cached
        client.

        Returns
        -------
        _MlflowClientLike
            The initialised MLflow client.

        Raises
        ------
        MlflowException
            If MLflow raises an error during initialisation.
        ConnectionError
        TimeoutError
        OSError
            Transport-level failures that should enter degraded mode.
        """
        if self._client is not None:
            if self._state.status == "degraded":
                self._maybe_reconnect_sync()
            if self._client is not None:
                return self._client

        client = self._client_factory(self._tracking_uri)
        exp = client.get_experiment_by_name(self._experiment_name)
        if exp:
            self._experiment_id = exp.experiment_id
        else:
            self._experiment_id = client.create_experiment(self._experiment_name)
        self._client = client
        return client

    @staticmethod
    def enable_system_metrics() -> None:
        """Enable MLflow system metrics logging (GPU utilisation, memory).

        Calls ``mlflow.enable_system_metrics_logging()`` once. Safe
        to call multiple times.
        """
        global _system_metrics_enabled  # pylint: disable=global-statement
        if _system_metrics_enabled:
            return
        try:
            mlflow.enable_system_metrics_logging()  # type: ignore[no-untyped-call]
            _system_metrics_enabled = True
        except Exception:
            pass

    async def capabilities(self) -> TrackingCapabilities:
        """Detect MLflow server capabilities for this tracking URI.

        Returns
        -------
        TrackingCapabilities
            Detected capabilities (genai dataset support, server
            backend flag, MLflow version).
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: detect_capabilities(self._tracking_uri)
        )

    ########################################################################
    # Run lifecycle
    ########################################################################

    async def start_run(
        self,
        *,
        run_name: str | None = None,
        params: dict[str, Any] | None = None,
        engine_backend: str,
        device: str,
    ) -> str:
        """Create a new MLflow run and log parameters.

        Handles connection errors gracefully by entering degraded mode.

        Parameters
        ----------
        run_name : str, optional
            Human-readable run name. Auto-generated if ``None``.
        params : dict[str, Any], optional
            Hyperparameters and config values to log.
        engine_backend : str
            Compute backend identifier (e.g. ``"stdlib"``, ``"torch"``).
        device : str
            Device identifier (e.g. ``"cpu"``, ``"cuda:0"``, ``"mps"``).

        Returns
        -------
        str
            The MLflow run ID, or empty string if degraded.
        """
        if self._state.status == "degraded":
            return ""

        loop = asyncio.get_event_loop()

        try:
            async with self._lock:
                client = await loop.run_in_executor(None, self._lazy_init)
            effective_run_name = (
                run_name or f"run-{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}"
            )

            mlflow_run = await loop.run_in_executor(
                None,
                lambda: client.create_run(
                    self._experiment_id,
                    run_name=effective_run_name,
                ),
            )
            run_id = str(mlflow_run.info.run_id)

            mlflow_params = []
            if params:
                for k, v in params.items():
                    if v is not None:
                        mlflow_params.append(
                            mlflow.entities.Param(k, str(v))  # type: ignore[no-untyped-call]
                        )
            mlflow_params.append(
                mlflow.entities.Param("engine_backend", engine_backend)  # type: ignore[no-untyped-call]
            )
            mlflow_params.append(
                mlflow.entities.Param("device", device)  # type: ignore[no-untyped-call]
            )

            if mlflow_params:
                await loop.run_in_executor(
                    None,
                    lambda: client.log_batch(run_id=run_id, params=mlflow_params),
                )

            return run_id

        except _TRANSIENT_EXCEPTIONS as exc:
            reason, msg = self._classify_exception(exc)
            async with self._lock:
                self._state = DegradedState.degraded(reason, msg)
            logger.warning(
                "Tracking service entered degraded mode: %s — %s",
                reason.value,
                msg,
            )
            return ""

    async def log_metric(
        self, run_id: str, key: str, value: float, step: int | None = None
    ) -> None:
        """Log a metric to an MLflow run.

        Parameters
        ----------
        run_id : str
            The MLflow run ID.
        key : str
            Metric name.
        value : float
            Metric value.
        step : int, optional
            Metric step (batch/epoch number). Defaults to ``None``.

        Raises
        ------
        ValueError
            If *run_id* is empty.
        """
        if self._state.status == "degraded":
            return
        if not run_id:
            raise ValueError("run_id must not be empty")
        loop = asyncio.get_event_loop()
        try:
            client = self._client
            if client is not None:
                await loop.run_in_executor(
                    None, lambda: client.log_metric(run_id, key, value, step=step)
                )
        except _TRANSIENT_EXCEPTIONS:
            pass

    async def log_final_metric(self, run_id: str, key: str, value: float) -> None:
        """Log a final metric (no step) to an MLflow run.

        Parameters
        ----------
        run_id : str
            The MLflow run ID.
        key : str
            Metric name.
        value : float
            Metric value.

        Raises
        ------
        ValueError
            If *run_id* is empty.
        """
        if self._state.status == "degraded":
            return
        if not run_id:
            raise ValueError("run_id must not be empty")
        await self.log_metric(run_id, key, value)

    async def finish_run(self, run_id: str) -> None:
        """Mark an MLflow run as finished.

        Parameters
        ----------
        run_id : str
            The MLflow run ID.

        Raises
        ------
        ValueError
            If *run_id* is empty.
        """
        if self._state.status == "degraded":
            return
        if not run_id:
            raise ValueError("run_id must not be empty")
        loop = asyncio.get_event_loop()
        try:
            client = self._client
            if client is not None:
                await loop.run_in_executor(
                    None, lambda: client.set_terminated(run_id, status="FINISHED")
                )
        except _TRANSIENT_EXCEPTIONS:
            pass

    async def fail_run(self, run_id: str, *, _reason: str | None = None) -> None:
        """Mark an MLflow run as failed.

        Parameters
        ----------
        run_id : str
            The MLflow run ID.
        reason : str, optional
            Optional failure reason. Defaults to ``None``.

        Raises
        ------
        ValueError
            If *run_id* is empty.
        """
        if self._state.status == "degraded":
            return
        if not run_id:
            raise ValueError("run_id must not be empty")
        loop = asyncio.get_event_loop()
        try:
            client = self._client
            if client is not None:
                await loop.run_in_executor(
                    None, lambda: client.set_terminated(run_id, status="FAILED")
                )
        except _TRANSIENT_EXCEPTIONS:
            pass

    async def set_tag(self, run_id: str, key: str, value: str) -> None:
        """Set a tag on an MLflow run.

        Parameters
        ----------
        run_id : str
            The MLflow run ID.
        key : str
            Tag key.
        value : str
            Tag value.

        Raises
        ------
        ValueError
            If *run_id* is empty.
        """
        if self._state.status == "degraded":
            return
        if not run_id:
            raise ValueError("run_id must not be empty")
        loop = asyncio.get_event_loop()
        try:
            client = self._client
            if client is not None:
                await loop.run_in_executor(
                    None, lambda: client.set_tag(run_id, key, value)
                )
        except _TRANSIENT_EXCEPTIONS:
            pass

    ########################################################################
    # Artifacts
    ########################################################################

    async def log_artifacts(
        self,
        run_id: str,
        *,
        model_path: str | None = None,
        safetensors_path: str | None = None,
        config_path: str | None = None,
        tokenizer_path: str | None = None,
        mlmodel_path: str | None = None,
        conda_path: str | None = None,
        _samples: str | None = None,
        _vocab: Any = None,
    ) -> None:
        """Log file artifacts to an MLflow run.

        Parameters
        ----------
        run_id : str
            The MLflow run ID.
        model_path : str, optional
            Path to the model JSON file.
        safetensors_path : str, optional
            Path to the safetensors file.
        config_path : str, optional
            Path to the config JSON file.
        tokenizer_path : str, optional
            Path to the tokenizer JSON file.
        mlmodel_path : str, optional
            Path to the MLmodel YAML file.
        conda_path : str, optional
            Path to the conda YAML file.
        samples : str, optional
            Path to a samples file.
        vocab : Any, optional
            Path to a vocabulary file (legacy parameter).

        Raises
        ------
        ValueError
            If *run_id* is empty.
        """
        if self._state.status == "degraded":
            return
        if not run_id:
            raise ValueError("run_id must not be empty")
        loop = asyncio.get_event_loop()
        try:
            client = self._client
            if client is not None:
                if model_path:
                    await loop.run_in_executor(
                        None, lambda: client.log_artifact(run_id, model_path)
                    )
                if safetensors_path:
                    await loop.run_in_executor(
                        None,
                        lambda: client.log_artifact(run_id, safetensors_path),
                    )
                if config_path:
                    await loop.run_in_executor(
                        None,
                        lambda: client.log_artifact(run_id, config_path),
                    )
                if tokenizer_path:
                    await loop.run_in_executor(
                        None,
                        lambda: client.log_artifact(run_id, tokenizer_path),
                    )
                if mlmodel_path:
                    await loop.run_in_executor(
                        None,
                        lambda: client.log_artifact(run_id, mlmodel_path),
                    )
                if conda_path:
                    await loop.run_in_executor(
                        None,
                        lambda: client.log_artifact(run_id, conda_path),
                    )
        except _TRANSIENT_EXCEPTIONS:
            pass

    async def log_artifact_dir(
        self,
        run_id: str,
        local_dir: str,
        artifact_path: str | None = None,
    ) -> None:
        """Log an entire directory of artifacts to an MLflow run.

        Uses ``MlflowClient.log_artifacts()`` to upload all files in
        *local_dir* to the run's artifact URI.  This is the correct way
        to log a multi-file export (safetensors + config + tokenizer)
        as a single artifact group.

        Parameters
        ----------
        run_id : str
            The MLflow run ID.
        local_dir : str
            Path to the local directory containing artifact files.
        artifact_path : str, optional
            Optional sub-path within the run's artifact directory.
            Defaults to ``None`` (root of the run's artifact store).

        Raises
        ------
        ValueError
            If *run_id* is empty.
        """
        if self._state.status == "degraded":
            return
        if not run_id:
            raise ValueError("run_id must not be empty")
        loop = asyncio.get_event_loop()
        try:
            client = self._client
            if client is not None:
                await loop.run_in_executor(
                    None,
                    lambda: client.log_artifacts(
                        run_id, local_dir, artifact_path=artifact_path
                    ),
                )
        except _TRANSIENT_EXCEPTIONS:
            pass

    ########################################################################
    # Dataset / Corpus input logging
    ########################################################################

    async def log_dataset_input(
        self,
        run_id: str,
        *,
        dataset_id: int,
        role: str = "training",
        session: AsyncSession | None = None,
    ) -> str:
        """Log a dataset as an MLflow dataset input for a run.

        Parameters
        ----------
        run_id : str
            The MLflow run ID.
        dataset_id : int
            The dataset ID.
        role : str
            Input role (e.g. ``"training"``). Defaults to ``"training"``.
        session : AsyncSession, optional
            Reusable DB session. Creates a new one if not provided.

        Returns
        -------
        str
            Content digest of the dataset, or empty string on failure.

        Raises
        ------
        ValueError
            If *run_id* is empty.
        """
        if self._state.status == "degraded":
            return ""
        if not run_id:
            raise ValueError("run_id must not be empty")
        if session is not None:
            try:
                resolver = MlflowInputResolver(session)
                mlflow_ds, digest = await resolver.resolve_dataset(
                    dataset_id, role=role
                )
                client = self._client
                assert client is not None
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: client.log_input(  # type: ignore[union-attr]
                        run_id=run_id, dataset=mlflow_ds, context=role
                    ),
                )
                return digest
            except _TRANSIENT_EXCEPTIONS:
                return ""
        else:
            async with AsyncSessionLocal() as sess:
                try:
                    resolver = MlflowInputResolver(sess)
                    mlflow_ds, digest = await resolver.resolve_dataset(
                        dataset_id, role=role
                    )
                    client = self._client
                    assert client is not None
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: client.log_input(
                            run_id=run_id, dataset=mlflow_ds, context=role
                        ),
                    )
                    return digest
                except _TRANSIENT_EXCEPTIONS:
                    return ""

    async def log_corpus_input(
        self,
        run_id: str,
        *,
        corpus_id: int,
        session: AsyncSession | None = None,
    ) -> str:
        """Log a corpus as an MLflow dataset input for a run.

        Parameters
        ----------
        run_id : str
            The MLflow run ID.
        corpus_id : int
            The corpus ID.
        session : AsyncSession, optional
            Reusable DB session. Creates a new one if not provided.

        Returns
        -------
        str
            Content digest of the corpus, or empty string on failure.

        Raises
        ------
        ValueError
            If *run_id* is empty.
        """
        if self._state.status == "degraded":
            return ""
        if not run_id:
            raise ValueError("run_id must not be empty")
        if session is not None:
            try:
                resolver = MlflowInputResolver(session)
                meta_ds, artifact_paths, digest = await resolver.resolve_corpus(
                    corpus_id
                )
                client = self._client
                assert client is not None
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: client.log_input(  # type: ignore[union-attr]
                        run_id=run_id, dataset=meta_ds, context="corpus"
                    ),
                )
                for artifact_path in artifact_paths:
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda p=artifact_path: client.log_artifact(run_id, p),  # type: ignore[misc]
                    )
                return digest
            except _TRANSIENT_EXCEPTIONS:
                return ""
        else:
            async with AsyncSessionLocal() as sess:
                try:
                    resolver = MlflowInputResolver(sess)
                    meta_ds, artifact_paths, digest = await resolver.resolve_corpus(
                        corpus_id
                    )
                    client = self._client
                    assert client is not None
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: client.log_input(
                            run_id=run_id, dataset=meta_ds, context="corpus"
                        ),
                    )
                    for artifact_path in artifact_paths:
                        await asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda p=artifact_path: client.log_artifact(run_id, p),  # type: ignore[misc]
                        )
                    return digest
                except _TRANSIENT_EXCEPTIONS:
                    return ""

    ########################################################################
    # Evaluation datasets
    ########################################################################

    async def create_eval_dataset(
        self,
        *,
        name: str,
        tags: dict[str, str] | None = None,
    ) -> Any:
        """Create a managed MLflow evaluation dataset.

        Requires MLflow 3.x with a SQL-backed server.

        Parameters
        ----------
        name : str
            Dataset name.
        tags : dict[str, str], optional
            Optional tags for the dataset.

        Returns
        -------
        Any
            The created MLflow dataset object.

        Raises
        ------
        CapabilityUnavailable
            If genai datasets are not supported by the server.
        """
        caps = await self.capabilities()
        if not caps.genai_datasets:
            raise CapabilityUnavailable(
                "Managed evaluation datasets require MLflow 3.x with a SQL-backed server. "
                f"genai_datasets={caps.genai_datasets}, server_backed={caps.server_backed}"
            )
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: _create_dataset_sync(name, tags),
        )

    async def append_eval_records(
        self, *, name: str, records: list[dict[str, Any]]
    ) -> int:
        """Append evaluation records to a managed MLflow dataset.

        Parameters
        ----------
        name : str
            Dataset name.
        records : list[dict]
            Evaluation records to append.

        Returns
        -------
        int
            Number of records appended.

        Raises
        ------
        CapabilityUnavailable
            If genai datasets are not supported.
        """
        caps = await self.capabilities()
        if not caps.genai_datasets:
            raise CapabilityUnavailable(
                "Managed evaluation datasets require MLflow 3.x with a SQL-backed server. "
                f"genai_datasets={caps.genai_datasets}, server_backed={caps.server_backed}"
            )
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: _append_records_sync(name, records),
        )

    async def get_eval_dataset(self, *, name: str) -> Any | None:
        """Retrieve a managed MLflow evaluation dataset by name.

        Parameters
        ----------
        name : str
            Dataset name.

        Returns
        -------
        Any or None
            The MLflow dataset object, or ``None`` if not found.

        Raises
        ------
        CapabilityUnavailable
            If genai datasets are not supported.
        """
        caps = await self.capabilities()
        if not caps.genai_datasets:
            raise CapabilityUnavailable(
                "Managed evaluation datasets require MLflow 3.x with a SQL-backed server. "
                f"genai_datasets={caps.genai_datasets}, server_backed={caps.server_backed}"
            )
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: _get_dataset_sync(name),
        )

    ########################################################################
    # Orphan reconciliation
    ########################################################################

    async def reconcile_orphans(self) -> list[str]:
        """Reconcile orphaned RUNNING MLflow runs by marking them KILLED.

        Finds all runs in the ``"RUNNING"`` status for this experiment
        and sets them to ``"KILLED"``. Useful for server restart cleanup.

        Returns
        -------
        list[str]
            List of reconciled MLflow run IDs.
        """
        if self._client is None:
            self._lazy_init()
        loop = asyncio.get_event_loop()
        reconciled: list[str] = []
        try:
            client = self._client
            if client is not None and self._experiment_id is not None:
                runs = await loop.run_in_executor(
                    None,
                    lambda: client.search_runs(
                        experiment_ids=[self._experiment_id],
                        filter_string="attributes.status = 'RUNNING'",
                    ),
                )
                for run in runs:
                    await loop.run_in_executor(
                        None,
                        lambda rid=run.info.run_id: client.set_terminated(  # type: ignore[misc]
                            rid, status="KILLED"
                        ),
                    )
                    reconciled.append(run.info.run_id)
        except _TRANSIENT_EXCEPTIONS:
            pass
        return reconciled

    ########################################################################
    # Safetensors artifact query
    ########################################################################

    async def get_safetensors_artifacts(self, run_id: str) -> dict[str, Any]:
        """Query MLflow for safetensors artifact info for a given run.

        Returns dict with keys:
          available: bool
          files: list of {path, file_size, is_safetensors, is_config, is_tokenizer}
          error: str or None

        Raises
        ------
        ValueError
            If *run_id* is empty.
        """
        if self._state.status == "degraded":
            return {"available": False, "files": [], "error": None}
        if not run_id:
            raise ValueError("run_id must not be empty")
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, self._lazy_init)
            client = self._client
            if client is None:
                return {
                    "available": False,
                    "files": [],
                    "error": "client not initialized",
                }
            artifacts = await loop.run_in_executor(
                None, lambda: client.list_artifacts(run_id)
            )
            safetensors_files = []
            for a in artifacts:
                if a.path.endswith(".safetensors"):
                    safetensors_files.append(
                        {
                            "path": a.path,
                            "file_size": (
                                a.file_size if hasattr(a, "file_size") else None
                            ),
                            "is_safetensors": True,
                            "is_config": False,
                            "is_tokenizer": False,
                        }
                    )
                elif a.path.endswith("config.json"):
                    safetensors_files.append(
                        {
                            "path": a.path,
                            "file_size": (
                                a.file_size if hasattr(a, "file_size") else None
                            ),
                            "is_safetensors": False,
                            "is_config": True,
                            "is_tokenizer": False,
                        }
                    )
                elif a.path.endswith("tokenizer.json"):
                    safetensors_files.append(
                        {
                            "path": a.path,
                            "file_size": (
                                a.file_size if hasattr(a, "file_size") else None
                            ),
                            "is_safetensors": False,
                            "is_config": False,
                            "is_tokenizer": True,
                        }
                    )
            return {
                "available": any(f["is_safetensors"] for f in safetensors_files),
                "files": safetensors_files,
                "error": None,
            }
        except _TRANSIENT_EXCEPTIONS as e:
            return {"available": False, "files": [], "error": str(e)}

    @staticmethod
    def _sanitize_model_name(name: str) -> str:
        """MLflow model registry rejects names containing '/' or ':'."""
        return name.replace("/", "-").replace(":", "-")

    ########################################################################
    # Model registry
    ########################################################################

    async def register_source_model(
        self,
        *,
        run_id: str,
        name: str | None = None,
        dataset_id: int | None = None,
        corpus_id: int | None = None,
        artifact_path: str = "model.json",
    ) -> dict[str, Any]:
        """Register the model source in the MLflow Model Registry.

        Parameters
        ----------
        run_id : str
            MLflow run ID that produced the model.
        name : str, optional
            Explicit model name. Defaults to ``None``.
        dataset_id : int, optional
            Dataset ID for auto-generated model name.
            Defaults to ``None``.
        corpus_id : int, optional
            Corpus ID for auto-generated model name.
            Defaults to ``None``.
        artifact_path : str
            Path to the model artifact within the run.
            Defaults to ``"model.json"``.

        Returns
        -------
        dict
            Result dict from the MLflow registry operation, or empty
            dict if in degraded mode.

        Raises
        ------
        ValueError
            If *run_id* is empty.
        """
        if self._state.status == "degraded":
            return {}
        if not run_id:
            raise ValueError("run_id must not be empty")
        if name:
            registry_name = self._sanitize_model_name(name)
        elif dataset_id is not None:
            registry_name = f"dataset-{dataset_id}"
        elif corpus_id is not None:
            registry_name = f"corpus-{corpus_id}"
        else:
            registry_name = "default-source"

        loop = asyncio.get_event_loop()
        client = self._client
        if client is None:
            return {}

        try:
            await loop.run_in_executor(
                None,
                lambda: client.create_registered_model(registry_name),
            )
        except _TRANSIENT_EXCEPTIONS:
            pass

        version = await loop.run_in_executor(
            None,
            lambda: client.create_model_version(
                name=registry_name,
                source=f"runs:/{run_id}/{artifact_path}",
                run_id=run_id,
            ),
        )
        return {
            "name": registry_name,
            "version": version.version if hasattr(version, "version") else str(version),
            "run_id": run_id,
            "source": f"runs:/{run_id}/{artifact_path}",
        }

    ########################################################################
    # Lifecycle events
    ########################################################################

    async def log_dataset_lifecycle_event(
        self,
        *,
        dataset_id: int,
        event_type: str,
        params: dict[str, Any] | None = None,
    ) -> str:
        """Create a short MLflow run recording a dataset lifecycle event.

        Args:
            dataset_id: Dataset ID
            event_type: One of "create", "import", "curate", "update", "delete"
            params: Optional metadata params to log (vocab_size, sample_count, operation_type, etc.)

        Returns: MLflow run_id or "" if degraded
        """
        if self._state.status == "degraded":
            return ""

        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, self._lazy_init)
        except _TRANSIENT_EXCEPTIONS as exc:
            reason, msg = self._classify_exception(exc)
            async with self._lock:
                self._state = DegradedState.degraded(reason, msg)
            logger.warning(
                "Tracking service entered degraded mode: %s — %s",
                reason.value,
                msg,
            )
            return ""

        run_id = await self.start_run(
            run_name=f"dataset-{event_type}-{dataset_id}",
            params=params,
            engine_backend="dataset",
            device="n/a",
        )
        if not run_id:
            return ""

        await self.set_tag(run_id, TAG_ENTITY_TYPE, "dataset")
        await self.set_tag(run_id, TAG_ENTITY_ID, str(dataset_id))
        await self.set_tag(run_id, TAG_EVENT, f"dataset-{event_type}")

        await self.finish_run(run_id)
        return run_id

    async def log_corpus_lifecycle_event(
        self,
        *,
        corpus_id: int,
        event_type: str,
        params: dict[str, Any] | None = None,
        tags: dict[str, str] | None = None,
    ) -> str:
        """Create a short MLflow run recording a corpus lifecycle event.

        Args:
            corpus_id: Corpus ID
            event_type: One of "create", "fork", "ingest", "delete"
            params: Optional metadata params (file_count, document_count, language_map, etc.)
            tags: Optional additional tags (e.g. parent_corpus_id for forks)

        Returns: MLflow run_id or "" if degraded
        """
        if self._state.status == "degraded":
            return ""

        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, self._lazy_init)
        except _TRANSIENT_EXCEPTIONS as exc:
            reason, msg = self._classify_exception(exc)
            async with self._lock:
                self._state = DegradedState.degraded(reason, msg)
            logger.warning(
                "Tracking service entered degraded mode: %s — %s",
                reason.value,
                msg,
            )
            return ""

        run_id = await self.start_run(
            run_name=f"corpus-{event_type}-{corpus_id}",
            params=params,
            engine_backend="corpus",
            device="n/a",
        )
        if not run_id:
            return ""

        await self.set_tag(run_id, TAG_ENTITY_TYPE, "corpus")
        await self.set_tag(run_id, TAG_ENTITY_ID, str(corpus_id))
        await self.set_tag(run_id, TAG_EVENT, f"corpus-{event_type}")

        if tags:
            for k, v in tags.items():
                await self.set_tag(run_id, k, v)

        await self.finish_run(run_id)
        return run_id

    ########################################################################
    # Query methods
    ########################################################################

    async def list_experiments(
        self,
        max_results: int = 100,
    ) -> list[dict[str, Any]]:
        """Query all MLflow runs for the 'anvil' experiment.

        Returns list of dicts with keys matching the current GET /v1/experiments response shape.

        Raises
        ------
        ValueError
            If *run_id* is empty.
        """
        if self._state.status == "degraded":
            return []
        loop = asyncio.get_event_loop()
        try:
            client = await loop.run_in_executor(None, self._lazy_init)
            if client is None or not self._experiment_id:
                return []
        except _TRANSIENT_EXCEPTIONS:
            return []

        try:
            runs = await loop.run_in_executor(
                None,
                lambda: client.search_runs(
                    experiment_ids=[self._experiment_id],
                    order_by=["attributes.start_time DESC"],
                    max_results=max_results,
                ),
            )
        except _TRANSIENT_EXCEPTIONS:
            return []

        result = []
        for run in runs:
            tags = dict(run.data.tags)
            params = dict(run.data.params)
            metrics = dict(run.data.metrics)

            # Skip lifecycle event runs (dataset-*, corpus-*) which have
            # engine_backend='dataset' or 'corpus' — they are internal
            # metadata, not user-facing training experiments.
            engine_backend = params.get("engine_backend", "")
            if engine_backend in ("dataset", "corpus"):
                continue

            # Parse anvil.experiment_id tag (may be missing for very old runs)
            exp_id_str = tags.get("anvil.experiment_id", "")
            try:
                exp_id = int(exp_id_str)
            except (ValueError, TypeError):
                exp_id = None

            raw_status = (run.info.status or "RUNNING").lower()
            result.append(
                {
                    "id": exp_id,
                    "status": raw_status,
                    "run_name": run.data.tags.get("mlflow.runName", "") or "",
                    "final_loss": metrics.get("final_loss"),
                    "mlflow_run_id": run.info.run_id,
                    "dataset_name": tags.get("anvil.dataset.name"),
                    "dataset_id": params.get("dataset_id"),
                    "corpus_id": params.get("corpus_id"),
                    "input_digest": tags.get("anvil.input_digest"),
                    "input_role": tags.get("anvil.input_role") or "training",
                    "engine_backend": params.get("engine_backend", ""),
                    "device": params.get("device", ""),
                    "created_at": (
                        str(run.info.start_time) if run.info.start_time else ""
                    ),
                    "config_id": None,
                    "artifact_available": False,
                }
            )
        return result

    async def get_experiment(
        self,
        experiment_id: int,
    ) -> dict[str, Any] | None:
        """Find an MLflow run by its anvil.experiment_id tag.

        Returns the same dict shape as list_experiments, plus extra detail fields,
        or None if not found.
        """
        if self._state.status == "degraded":
            return None
        loop = asyncio.get_event_loop()
        try:
            client = await loop.run_in_executor(None, self._lazy_init)
            if client is None or not self._experiment_id:
                return None
        except _TRANSIENT_EXCEPTIONS:
            return None

        try:
            runs = await loop.run_in_executor(
                None,
                lambda: client.search_runs(
                    experiment_ids=[self._experiment_id],
                    filter_string=f"tags.`anvil.experiment_id` = '{experiment_id}'",
                    max_results=1,
                ),
            )
        except _TRANSIENT_EXCEPTIONS:
            return None

        if not runs:
            return None

        run = runs[0]
        tags = dict(run.data.tags)
        params = dict(run.data.params)
        metrics = dict(run.data.metrics)

        raw_status = (run.info.status or "RUNNING").lower()
        return {
            "id": experiment_id,
            "status": raw_status,
            "run_name": run.data.tags.get("mlflow.runName", "") or "",
            "final_loss": metrics.get("final_loss"),
            "config_id": None,
            "mlflow_run_id": run.info.run_id,
            "dataset_name": tags.get("anvil.dataset.name"),
            "created_at": str(run.info.start_time) if run.info.start_time else "",
            "completed_at": str(run.info.end_time) if run.info.end_time else None,
            "input_digest": tags.get("anvil.input_digest"),
            "input_role": tags.get("anvil.input_role"),
            "engine_backend": params.get("engine_backend", ""),
            "device": params.get("device", ""),
            "params": params,
            "metrics": metrics,
            "tags": tags,
        }

    async def list_registered_models(
        self, search: str | None = None
    ) -> list[dict[str, Any]]:
        """Query MLflow model registry for all registered models, enriched with run metadata.

        Returns a list of dicts, each with:
          id:         local experiment_id (int) or None if not found in local DB
          name:       MLflow registered model name (string)
          version:    latest version number (int)
          run_id:     MLflow run ID (string)
          final_loss: final_loss metric from the run (float or None)
          created_at: MLflow model creation timestamp (string or None)
          total_versions: total number of versions (int or 0)
        """
        if self._state.status == "degraded":
            return []
        loop = asyncio.get_event_loop()
        try:
            client = await loop.run_in_executor(None, self._lazy_init)
            if client is None:
                return []
        except _TRANSIENT_EXCEPTIONS:
            return []

        try:
            filter_string = None
            if search:
                filter_string = f"name LIKE '%{search}%'"
            registered_models = await loop.run_in_executor(
                None,
                lambda: client.search_registered_models(
                    filter_string=filter_string,
                ),
            )
        except _TRANSIENT_EXCEPTIONS:
            return []

        result = []
        for rm in registered_models:
            try:
                latest_versions = await loop.run_in_executor(
                    None,
                    lambda name=rm.name: client.search_model_versions(f"name='{name}'"),  # type: ignore[misc]
                )
                if not latest_versions:
                    continue
                sorted_versions = sorted(
                    latest_versions, key=lambda v: int(v.version), reverse=True
                )
                latest = sorted_versions[0]

                final_loss = None
                experiment_id = None
                try:
                    run = await loop.run_in_executor(
                        None,
                        lambda rid=latest.run_id: client.get_run(rid),  # type: ignore[misc]
                    )
                    if run and run.data:
                        if run.data.metrics:
                            final_loss = run.data.metrics.get("final_loss")
                        raw = run.data.tags.get("anvil.experiment_id")
                        if raw is not None:
                            experiment_id = int(raw)
                except _TRANSIENT_EXCEPTIONS:
                    pass

                all_versions = await loop.run_in_executor(
                    None,
                    lambda name=rm.name: client.search_model_versions(f"name='{name}'"),  # type: ignore[misc]
                )
                total_versions = len(list(all_versions)) if all_versions else 0

                result.append(
                    {
                        "id": experiment_id,
                        "name": rm.name,
                        "description": (
                            rm.description if hasattr(rm, "description") else None
                        ),
                        "version": latest.version,
                        "latest_version": latest.version,
                        "run_id": latest.run_id,
                        "final_loss": final_loss,
                        "latest_loss": final_loss,
                        "created_at": (
                            str(latest.creation_timestamp)
                            if hasattr(latest, "creation_timestamp")
                            and latest.creation_timestamp
                            else None
                        ),
                        "total_versions": total_versions,
                    }
                )
            except _TRANSIENT_EXCEPTIONS:
                continue

        return result

    # ------------------------------------------------------------------
    # Evaluation-specific MLflow helpers (spec 054)
    # ------------------------------------------------------------------

    async def start_eval_run(
        self,
        *,
        run_name: str | None = None,
        model_id: int,
        base_model_id: int,
        adapter_id: str | None = None,
        tokenizer_family: str,
    ) -> str:
        """Start an MLflow run for a fine-tuned model evaluation.

        Reuses ``start_run`` with eval-specific tags for lineage tracing.

        Parameters
        ----------
        run_name : str, optional
            Optional human-readable run name.
        model_id : int
            ``ExternalModel.id`` of the fine-tuned model.
        base_model_id : int
            ``ExternalModel.id`` of the base model.
        adapter_id : str | None, optional
            Adapter ID if evaluating an adapter model. Defaults to ``None``.
        tokenizer_family : str
            Tokenizer family of the fine-tuned model.

        Returns
        -------
        str
            The MLflow run ID, or empty string if degraded.
        """
        run_id = await self.start_run(
            run_name=run_name or f"eval-{model_id}-vs-{base_model_id}",
            engine_backend="evaluation",
            device="cpu",
        )
        if not run_id:
            return ""

        await self.set_tag(run_id, "anvil.origin", "evaluation")
        await self.set_tag(run_id, TAG_ENTITY_TYPE, "evaluation")
        await self.set_tag(run_id, "anvil.base_model_ref", str(base_model_id))
        await self.set_tag(run_id, "anvil.fine_tuned_model_id", str(model_id))
        await self.set_tag(run_id, "anvil.tokenizer_family", tokenizer_family)
        await self.set_tag(run_id, "anvil.eval_status", EvaluationRunStatus.RUNNING)
        if adapter_id:
            await self.set_tag(run_id, "anvil.adapter_id", adapter_id)
        return run_id

    async def log_eval_metric(
        self,
        run_id: str,
        key: str,
        value: float,
        step: int | None = None,
    ) -> None:
        """Log a metric to an evaluation MLflow run.

        Convenience wrapper around ``log_metric``.

        Parameters
        ----------
        run_id : str
            The MLflow run ID.
        key : str
            Metric name.
        value : float
            Metric value.
        step : int, optional
            Metric step. Defaults to ``None``.
        """
        await self.log_metric(run_id, key, value, step=step)

    async def finish_eval_run(self, run_id: str) -> None:
        """Mark an evaluation MLflow run as completed.

        Parameters
        ----------
        run_id : str
            The MLflow run ID.
        """
        if run_id:
            await self.set_tag(
                run_id, "anvil.eval_status", EvaluationRunStatus.COMPLETED
            )
            await self.finish_run(run_id)

    async def fail_eval_run(self, run_id: str, *, reason: str | None = None) -> None:
        """Mark an evaluation MLflow run as failed.

        Parameters
        ----------
        run_id : str
            The MLflow run ID.
        reason : str, optional
            Failure reason. Defaults to ``None``.
        """
        if run_id:
            await self.set_tag(run_id, "anvil.eval_status", EvaluationRunStatus.FAILED)
            if reason:
                await self.set_tag(run_id, "anvil.eval_error", reason)
            await self.fail_run(run_id, _reason=reason)


def _create_dataset_sync(name: str, tags: dict[str, Any] | None) -> Any:
    if create_dataset is None:
        raise ImportError("mlflow.genai.datasets is not available")
    return create_dataset(name=name, tags=tags or {})


def _append_records_sync(name: str, records: list[dict[str, Any]]) -> int:
    """Synchronously append evaluation records to an MLflow dataset."""
    if get_dataset is None:
        raise ImportError("mlflow.genai.datasets is not available")
    ds = get_dataset(name=name)
    if ds is None:
        raise ValueError(f"Dataset '{name}' not found")
    ds.merge_records(records)
    return len(records)


def _get_dataset_sync(name: str) -> Any | None:
    """Synchronously retrieve an MLflow managed evaluation dataset by name."""
    if get_dataset is None:
        return None
    try:
        return get_dataset(name=name)
    except _TRANSIENT_EXCEPTIONS:
        return None
