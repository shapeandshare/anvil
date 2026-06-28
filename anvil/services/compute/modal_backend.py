# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Modal cloud compute backend.

Wraps a remote Modal function via submit-then-poll pattern (D3).

- ``is_available()`` checks whether the ``modal`` package is installed.
- ``run()`` submits a training job to Modal's cloud, polls for status,
  and returns a ``ComputeResult``.

MLflow logging happens **inside** the remote job (Q-B corrected), so the
backend only returns artifact URIs -- no local export is needed.
"""

import asyncio
from collections.abc import Callable
from typing import Any

from .compute_backend_result import ComputeBackendResult
from .compute_status import ComputeStatus
from .protocol import ProgressCallback, StopCheck
from .registry import register
from .registry_backend import RegistryBackend
from .result import ComputeResult
from .training_engine import TrainingEngine

#: Module-level flag so ``is_available()`` does not retry the import on
#: every call.  Set once at module load time.
_MODAL_AVAILABLE: bool = False
try:
    import modal

    _MODAL_AVAILABLE = True
except ImportError:
    pass


class ModalBackend:
    """Remote compute backend powered by Modal.

    Accepts an optional ``function_factory`` keyword argument for testing.
    In production, the factory is ``None`` and the backend builds the
    Modal function lazily inside ``run()``.

    The Modal function receives the training config plus the MLflow
    tracking URI via ``modal.Secret``.  The remote job is responsible
    for logging its own metrics and artifacts to MLflow.
    """

    #: Backend identifier used by the registry and resolution layer.
    name = RegistryBackend.MODAL

    def __init__(self, function_factory: Callable[[], Any] | None = None):
        """Initialise the Modal backend with an optional function factory.

        Parameters
        ----------
        function_factory : Callable[[], Any] | None, optional
            Factory callable that returns a Modal remote function.
            Used for testing with injected fakes.  ``None`` means the
            backend will construct the real Modal function at runtime.
        """
        self._function_factory = function_factory

    @staticmethod
    def is_available() -> bool:
        """Check whether the Modal cloud backend is available.

        Returns the module-level ``_MODAL_AVAILABLE`` flag, which is
        set once at import time to avoid repeated import attempts.

        Returns
        -------
        bool
            ``True`` if the ``modal`` package is installed.
        """
        return _MODAL_AVAILABLE

    async def run(
        self,
        docs: list[str],
        config: dict[str, Any],
        *,
        progress_callback: ProgressCallback,
        stop_check: StopCheck,
    ) -> ComputeResult:
        """Submit and monitor a training job on Modal's cloud.

        Resolves the remote function (either from an injected factory or
        by building it from the ``modal`` package), spawns the job, and
        polls until completion, failure, or user cancellation.

        Parameters
        ----------
        docs : list[str]
            Training documents (raw text strings).
        config : dict[str, Any]
            Hyperparameter dictionary forwarded to the remote training
            function.
        progress_callback : ProgressCallback
            Callable invoked with ``(-1, 0.0)`` on submission and
            ``(0, 0.0)`` during polling to indicate the job is still
            running.
        stop_check : StopCheck
            Callable returning ``True`` if the user has requested
            cancellation.  Triggers a remote ``call.cancel()``.

        Returns
        -------
        ComputeResult
            Completed result with artifact URIs, or failed result with
            an error message.
        """
        loop = asyncio.get_event_loop()

        # --- resolve the remote function (injected fake or real Modal) ---
        if self._function_factory is not None:
            remote_fn = self._function_factory()
        else:
            # import-placement:allow -- modal is imported at module level above
            assert (
                _MODAL_AVAILABLE
            ), "modal package required when no function factory provided"
            remote_fn = self._build_remote_function(modal)  # type: ignore[possibly-unbound]

        # --- submit ---
        call = await loop.run_in_executor(None, lambda: remote_fn.spawn(docs, config))
        job_id: str = call.object_id

        if progress_callback is not None:
            progress_callback(-1, 0.0)  # step=-1 signals "submitted"

        # --- poll loop ---
        while True:
            if stop_check():
                # User requested cancellation
                await loop.run_in_executor(None, call.cancel)
                return ComputeResult(
                    status=ComputeStatus.FAILED,
                    error_message="Training cancelled by user",
                    remote_job_id=job_id,
                    exported_remotely=True,
                    backend=ComputeBackendResult.MODAL,
                    engine=TrainingEngine.TORCH,
                )

            status: str = await loop.run_in_executor(None, call.get_status)

            # Notify the caller of the current status
            if progress_callback is not None:
                progress_callback(0, 0.0)

            if status == "success":
                result_data: dict[str, Any] = await loop.run_in_executor(None, call.get)
                return ComputeResult(
                    status=ComputeStatus.COMPLETED,
                    exported_remotely=True,
                    artifact_uris=result_data.get("artifact_uris", {}),
                    remote_job_id=job_id,
                    remote_mlflow_run_id=result_data.get("mlflow_run_id"),
                    backend=ComputeBackendResult.MODAL,
                    engine=TrainingEngine.TORCH,
                )

            if status in ("failed", "error"):
                # MLflow status strings, not ComputeStatus
                error: str | None = await loop.run_in_executor(None, call.get_error)
                return ComputeResult(
                    status=ComputeStatus.FAILED,
                    error_message=str(error) if error else "Remote job failed",
                    remote_job_id=job_id,
                    exported_remotely=True,
                    backend=ComputeBackendResult.MODAL,
                    engine=TrainingEngine.TORCH,
                )

            await asyncio.sleep(2)

    # ------------------------------------------------------------------
    # _build_remote_function
    # ------------------------------------------------------------------
    @staticmethod
    def _build_remote_function(modal_module: Any) -> Any:
        """Construct the Modal function that runs training in the cloud.

        This is a separate method so it can be unit-tested or replaced
        by an injected factory.  It uses ``modal.App`` and the
        ``@app.function()`` decorator to define the remote workload.

        Parameters
        ----------
        modal_module : Any
            The imported ``modal`` package (or a test double conforming
            to the same interface).

        Returns
        -------
        Any
            A Modal-decorated function that accepts ``(docs, config)``
            and returns a dictionary with ``artifact_uris`` and
            ``mlflow_run_id``.
        """
        app = modal_module.App("anvil-training")

        @app.function(  # type: ignore[untyped-decorator]
            secrets=[modal_module.Secret.from_name("mlflow-secret")],
            timeout=3600,
        )
        def _train_remote(docs: list[str], config: dict[str, Any]) -> dict[str, Any]:
            """Train on Modal's cloud GPUs.

            MLflow tracking URI is injected via ``modal.Secret``.
            The job logs its own metrics and artifacts to MLflow.

            Parameters
            ----------
            docs : list[str]
                Training documents (raw text strings).
            config : dict[str, Any]
                Hyperparameter dictionary forwarded from the caller.

            Returns
            -------
            dict[str, Any]
                Dictionary with ``artifact_uris`` and ``mlflow_run_id``
                keys for downstream metadata registration.
            """
            # import-placement:allow -- Modal remote function runs in cloud
            import os

            # import-placement:allow -- Modal remote function runs in cloud
            import mlflow

            # import-placement:allow -- Modal remote function runs in cloud
            from ...core.torch_engine import train_torch

            mlflow_tracking_uri = os.environ.get(
                "MLFLOW_TRACKING_URI",
                os.environ.get("ANVIL_MLFLOW_URI", "http://127.0.0.1:5001"),
            )
            mlflow.set_tracking_uri(mlflow_tracking_uri)

            device = config.get("device", "cuda:0")

            with mlflow.start_run() as run:
                mlflow.log_params(
                    {
                        "num_steps": config.get("num_steps", 1000),
                        "n_embd": config.get("n_embd", 16),
                        "n_head": config.get("n_head", 4),
                        "n_layer": config.get("n_layer", 1),
                        "block_size": config.get("block_size", 16),
                        "learning_rate": config.get("learning_rate", 0.01),
                        "temperature": config.get("temperature", 0.5),
                        "backend": "modal",
                    }
                )

                _weights, final_loss, samples, uchars = train_torch(
                    docs,
                    device=device,
                    num_steps=config.get("num_steps", 1000),
                    n_embd=config.get("n_embd", 16),
                    n_head=config.get("n_head", 4),
                    n_layer=config.get("n_layer", 1),
                    block_size=config.get("block_size", 16),
                    learning_rate=config.get("learning_rate", 0.01),
                    temperature=config.get("temperature", 0.5),
                )

                mlflow.log_metric("final_loss", final_loss)

                # Log samples as an artifact
                # import-placement:allow -- Modal remote function runs in cloud
                import tempfile

                with tempfile.TemporaryDirectory() as tmpdir:
                    samples_path = os.path.join(tmpdir, "samples.txt")
                    with open(samples_path, "w", encoding="utf-8") as f:
                        f.write("\n".join(samples))
                    mlflow.log_artifact(samples_path)

                # Log model artifacts from the exported weights
                # import-placement:allow -- Modal remote function runs in cloud
                from ..export import SafetensorsExportService

                export_svc = SafetensorsExportService()
                with tempfile.TemporaryDirectory() as tmpdir:
                    # Build a CPU LlamaModel from the exported weights
                    # import-placement:allow -- Modal remote function runs in cloud
                    from ...core.engine import LlamaModel

                    model = LlamaModel(
                        vocab_size=len(uchars) + 1,
                        n_embd=config.get("n_embd", 16),
                        n_head=config.get("n_head", 4),
                        n_layer=config.get("n_layer", 1),
                        block_size=config.get("block_size", 16),
                    )
                    # import-placement:allow -- Modal remote function runs in cloud
                    from .local import _load_weights_into_model

                    _load_weights_into_model(model, _weights)

                    export_result = export_svc.export(model, tmpdir, uchars)
                    if not export_result["error"]:
                        if export_result["safetensors_path"]:
                            mlflow.log_artifact(export_result["safetensors_path"])
                        if export_result["config_path"]:
                            mlflow.log_artifact(export_result["config_path"])
                        if export_result["tokenizer_path"]:
                            mlflow.log_artifact(export_result["tokenizer_path"])

                return {
                    "artifact_uris": {
                        "mlflow_run_id": run.info.run_id,
                    },
                    "mlflow_run_id": run.info.run_id,
                }

        return _train_remote


# ── auto-register ──────────────────────────────────────────────────────


def _modal_factory() -> ModalBackend:
    """Factory callable for the Modal cloud backend.

    Returns
    -------
    ModalBackend
        A new instance of the Modal compute backend.
    """
    return ModalBackend()


register(RegistryBackend.MODAL, _modal_factory)  # type: ignore[arg-type]
