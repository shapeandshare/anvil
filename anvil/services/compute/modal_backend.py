"""Modal cloud compute backend.

Wraps a remote Modal function via submit-then-poll pattern (D3).

- ``is_available()`` checks whether the ``modal`` package is installed.
- ``run()`` submits a training job to Modal's cloud, polls for status,
  and returns a ``ComputeResult``.

MLflow logging happens **inside** the remote job (Q-B corrected), so the
backend only returns artifact URIs — no local export is needed.
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable

from anvil.services.compute.protocol import ComputeBackendProtocol, ProgressCallback, StopCheck
from anvil.services.compute.registry import register
from anvil.services.compute.result import ComputeResult, ComputeStatus

# Module-level flag so is_available() does not retry the import on every call.
_MODAL_AVAILABLE: bool = False
try:
    import modal  # noqa: F401

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

    name = "modal"

    def __init__(self, function_factory: Callable[[], Any] | None = None):
        self._function_factory = function_factory

    @staticmethod
    def is_available() -> bool:
        return _MODAL_AVAILABLE

    async def run(
        self,
        docs: list[str],
        config: dict[str, Any],
        *,
        progress_callback: ProgressCallback,
        stop_check: StopCheck,
    ) -> ComputeResult:
        loop = asyncio.get_event_loop()

        # --- resolve the remote function (injected fake or real Modal) ---
        if self._function_factory is not None:
            remote_fn = self._function_factory()
        else:
            import modal  # lazy import — only needed without injected factory

            remote_fn = self._build_remote_function(modal)

        # --- submit ---
        call = await loop.run_in_executor(
            None, lambda: remote_fn.spawn(docs, config)
        )
        job_id: str = call.object_id

        if progress_callback is not None:
            progress_callback(-1, 0.0)  # step=-1 signals "submitted"

        # --- poll loop ---
        while True:
            if stop_check is not None and stop_check():
                # User requested cancellation
                await loop.run_in_executor(None, lambda: call.cancel())
                return ComputeResult(
                    status=ComputeStatus.FAILED,
                    error_message="Training cancelled by user",
                    remote_job_id=job_id,
                    exported_remotely=True,
                    backend="modal",
                    engine="torch",
                )

            status: str = await loop.run_in_executor(
                None, lambda: call.get_status()
            )

            # Notify the caller of the current status
            if progress_callback is not None:
                progress_callback(0, 0.0)

            if status == "success":
                result_data: dict = await loop.run_in_executor(
                    None, lambda: call.get()
                )
                return ComputeResult(
                    status=ComputeStatus.COMPLETED,
                    exported_remotely=True,
                    artifact_uris=result_data.get("artifact_uris", {}),
                    remote_job_id=job_id,
                    remote_mlflow_run_id=result_data.get("mlflow_run_id"),
                    backend="modal",
                    engine="torch",
                )

            if status in ("failed", "error"):
                error: str | None = await loop.run_in_executor(
                    None, lambda: call.get_error()
                )
                return ComputeResult(
                    status=ComputeStatus.FAILED,
                    error_message=str(error) if error else "Remote job failed",
                    remote_job_id=job_id,
                    exported_remotely=True,
                    backend="modal",
                    engine="torch",
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
        """
        from anvil.config import get_mlflow_uri

        app = modal_module.App("anvil-training")

        @app.function(
            secrets=[modal_module.Secret.from_name("mlflow-secret")],
            timeout=3600,
        )
        def _train_remote(
            docs: list[str], config: dict[str, Any]
        ) -> dict[str, Any]:
            """Train on Modal's cloud GPUs.

            MLflow tracking URI is injected via ``modal.Secret``.
            The job logs its own metrics and artifacts to MLflow.
            """
            import os

            import mlflow

            from anvil.core.torch_engine import train_torch

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
                import tempfile

                with tempfile.TemporaryDirectory() as tmpdir:
                    samples_path = os.path.join(tmpdir, "samples.txt")
                    with open(samples_path, "w") as f:
                        f.write("\n".join(samples))
                    mlflow.log_artifact(samples_path)

                # Log model artifacts from the exported weights
                from anvil.services.export import SafetensorsExportService

                export_svc = SafetensorsExportService()
                with tempfile.TemporaryDirectory() as tmpdir:
                    # Build a CPU LlamaModel from the exported weights
                    from anvil.core.engine import LlamaModel

                    model = LlamaModel(
                        vocab_size=len(uchars) + 1,
                        n_embd=config.get("n_embd", 16),
                        n_head=config.get("n_head", 4),
                        n_layer=config.get("n_layer", 1),
                        block_size=config.get("block_size", 16),
                    )
                    from anvil.services.compute.local import _load_weights_into_model

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
    return ModalBackend()


register("modal", _modal_factory)
