from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
from typing import Any

import mlflow.entities

from anvil.config import get_config
from anvil.services.mlflow_capabilities import (
    TrackingCapabilities,
    detect_capabilities,
)


class CapabilityUnavailable(Exception):
    pass


_system_metrics_enabled = False
_MlflowClientLike = Any


class TrackingService:
    def __init__(
        self,
        *,
        tracking_uri: str | None = None,
        experiment_name: str = "anvil",
        client_factory: Callable[[str], _MlflowClientLike] | None = None,
    ):
        cfg = get_config()
        self._tracking_uri = tracking_uri or cfg["mlflow_uri"]
        self._experiment_name = experiment_name
        self._degraded = False

        if client_factory is not None:
            from mlflow.tracking import MlflowClient

            self._client_factory: Callable[[str], _MlflowClientLike] = client_factory
        else:
            from mlflow.tracking import MlflowClient

            self._client_factory = MlflowClient

        self._client: _MlflowClientLike | None = None
        self._experiment_id: str | None = None

    def _lazy_init(self) -> _MlflowClientLike:
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

    @property
    def is_degraded(self) -> bool:
        return self._degraded

    @staticmethod
    def enable_system_metrics() -> None:
        global _system_metrics_enabled
        if _system_metrics_enabled:
            return
        try:
            import mlflow

            mlflow.enable_system_metrics_logging()
            _system_metrics_enabled = True
        except Exception:
            pass

    async def capabilities(self) -> TrackingCapabilities:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: detect_capabilities(self._tracking_uri)
        )

    async def start_run(
        self,
        *,
        run_name: str | None = None,
        params: dict[str, Any] | None = None,
        engine_backend: str,
        device: str,
    ) -> str:
        if self._degraded:
            return ""

        loop = asyncio.get_event_loop()

        try:
            client = await loop.run_in_executor(None, lambda: self._lazy_init())
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
                        mlflow_params.append(mlflow.entities.Param(k, str(v)))
            mlflow_params.append(
                mlflow.entities.Param("engine_backend", engine_backend)
            )
            mlflow_params.append(mlflow.entities.Param("device", device))

            if mlflow_params:
                await loop.run_in_executor(
                    None,
                    lambda: client.log_batch(run_id=run_id, params=mlflow_params),
                )

            return run_id

        except ConnectionError:
            self._degraded = True
            return ""
        except Exception:
            self._degraded = True
            return ""

    async def log_metric(
        self, run_id: str, key: str, value: float, step: int | None = None
    ) -> None:
        if self._degraded or not run_id:
            return
        loop = asyncio.get_event_loop()
        try:
            client = self._client
            if client is not None:
                await loop.run_in_executor(
                    None, lambda: client.log_metric(run_id, key, value, step=step)
                )
        except Exception:
            pass

    async def log_final_metric(self, run_id: str, key: str, value: float) -> None:
        if self._degraded or not run_id:
            return
        await self.log_metric(run_id, key, value)

    async def finish_run(self, run_id: str) -> None:
        if self._degraded or not run_id:
            return
        loop = asyncio.get_event_loop()
        try:
            client = self._client
            if client is not None:
                await loop.run_in_executor(
                    None, lambda: client.set_terminated(run_id, status="FINISHED")
                )
        except Exception:
            pass

    async def fail_run(self, run_id: str, *, reason: str | None = None) -> None:
        if self._degraded or not run_id:
            return
        loop = asyncio.get_event_loop()
        try:
            client = self._client
            if client is not None:
                await loop.run_in_executor(
                    None, lambda: client.set_terminated(run_id, status="FAILED")
                )
        except Exception:
            pass

    async def set_tag(self, run_id: str, key: str, value: str) -> None:
        if self._degraded or not run_id:
            return
        loop = asyncio.get_event_loop()
        try:
            client = self._client
            if client is not None:
                await loop.run_in_executor(
                    None, lambda: client.set_tag(run_id, key, value)
                )
        except Exception:
            pass

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
        samples: str | None = None,
        vocab: Any = None,
    ) -> None:
        if self._degraded or not run_id:
            return
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
        except Exception:
            pass

    async def log_dataset_input(
        self,
        run_id: str,
        *,
        dataset_id: int,
        role: str = "training",
        session: Any = None,
    ) -> str:
        if self._degraded or not run_id:
            return ""
        from anvil.services.mlflow_inputs import MlflowInputResolver

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
                    lambda: client.log_input(
                        run_id=run_id, dataset=mlflow_ds, context=role
                    ),
                )
                return digest
            except Exception:
                return ""
        else:
            from anvil.db.session import AsyncSessionLocal

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
                except Exception:
                    return ""

    async def log_corpus_input(
        self,
        run_id: str,
        *,
        corpus_id: int,
        session: Any = None,
    ) -> str:
        if self._degraded or not run_id:
            return ""
        from anvil.services.mlflow_inputs import MlflowInputResolver

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
                    lambda: client.log_input(
                        run_id=run_id, dataset=meta_ds, context="corpus"
                    ),
                )
                for artifact_path in artifact_paths:
                    await asyncio.get_event_loop().run_in_executor(
                        None, lambda p=artifact_path: client.log_artifact(run_id, p)
                    )
                return digest
            except Exception:
                return ""
        else:
            from anvil.db.session import AsyncSessionLocal

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
                            lambda p=artifact_path: client.log_artifact(run_id, p),
                        )
                    return digest
                except Exception:
                    return ""

    async def create_eval_dataset(
        self,
        *,
        name: str,
        tags: dict[str, str] | None = None,
    ) -> Any:
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

    async def append_eval_records(self, *, name: str, records: list[dict]) -> int:
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

    async def reconcile_orphans(self) -> list[str]:
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
                        lambda rid=run.info.run_id: client.set_terminated(
                            rid, status="KILLED"
                        ),
                    )
                    reconciled.append(run.info.run_id)
        except Exception:
            pass
        return reconciled

    async def get_safetensors_artifacts(self, run_id: str) -> dict:
        """Query MLflow for safetensors artifact info for a given run.

        Returns dict with keys:
          available: bool
          files: list of {path, file_size, is_safetensors, is_config, is_tokenizer}
          error: str or None
        """
        if self._degraded or not run_id:
            return {"available": False, "files": [], "error": None}
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, lambda: self._lazy_init())
            client = self._client
            if client is None:
                return {"available": False, "files": [], "error": "client not initialized"}
            artifacts = await loop.run_in_executor(
                None, lambda: client.list_artifacts(run_id)
            )
            safetensors_files = []
            for a in artifacts:
                if a.path.endswith(".safetensors"):
                    safetensors_files.append({
                        "path": a.path,
                        "file_size": a.file_size if hasattr(a, "file_size") else None,
                        "is_safetensors": True,
                        "is_config": False,
                        "is_tokenizer": False,
                    })
                elif a.path.endswith("config.json"):
                    safetensors_files.append({
                        "path": a.path,
                        "file_size": a.file_size if hasattr(a, "file_size") else None,
                        "is_safetensors": False,
                        "is_config": True,
                        "is_tokenizer": False,
                    })
                elif a.path.endswith("tokenizer.json"):
                    safetensors_files.append({
                        "path": a.path,
                        "file_size": a.file_size if hasattr(a, "file_size") else None,
                        "is_safetensors": False,
                        "is_config": False,
                        "is_tokenizer": True,
                    })
            return {
                "available": any(f["is_safetensors"] for f in safetensors_files),
                "files": safetensors_files,
                "error": None,
            }
        except Exception as e:
            return {"available": False, "files": [], "error": str(e)}

    @staticmethod
    def _sanitize_model_name(name: str) -> str:
        """MLflow model registry rejects names containing '/' or ':'."""
        return name.replace("/", "-").replace(":", "-")

    async def register_source_model(
        self,
        *,
        run_id: str,
        name: str | None = None,
        dataset_id: int | None = None,
        corpus_id: int | None = None,
        artifact_path: str = "model.json",
    ) -> dict:
        if self._degraded or not run_id:
            return {}
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
        except Exception:
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
        if self._degraded:
            return ""

        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, lambda: self._lazy_init())
        except Exception:
            self._degraded = True
            return ""

        run_id = await self.start_run(
            run_name=f"dataset-{event_type}-{dataset_id}",
            params=params,
            engine_backend="dataset",
            device="n/a",
        )
        if not run_id:
            return ""

        # Set tags for identification
        await self.set_tag(run_id, "anvil.entity_type", "dataset")
        await self.set_tag(run_id, "anvil.entity_id", str(dataset_id))
        await self.set_tag(run_id, "anvil.event", f"dataset-{event_type}")

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
        if self._degraded:
            return ""

        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, lambda: self._lazy_init())
        except Exception:
            self._degraded = True
            return ""

        run_id = await self.start_run(
            run_name=f"corpus-{event_type}-{corpus_id}",
            params=params,
            engine_backend="corpus",
            device="n/a",
        )
        if not run_id:
            return ""

        await self.set_tag(run_id, "anvil.entity_type", "corpus")
        await self.set_tag(run_id, "anvil.entity_id", str(corpus_id))
        await self.set_tag(run_id, "anvil.event", f"corpus-{event_type}")

        if tags:
            for k, v in tags.items():
                await self.set_tag(run_id, k, v)

        await self.finish_run(run_id)
        return run_id

    async def list_experiments(
        self,
        max_results: int = 100,
    ) -> list[dict]:
        """Query all MLflow runs for the 'anvil' experiment.

        Returns list of dicts with keys matching the current GET /v1/experiments response shape.
        """
        if self._degraded:
            return []
        loop = asyncio.get_event_loop()
        try:
            client = await loop.run_in_executor(None, lambda: self._lazy_init())
            if client is None or not self._experiment_id:
                return []
        except Exception:
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
        except Exception:
            return []

        result = []
        for run in runs:
            tags = dict(run.data.tags)
            params = dict(run.data.params)
            metrics = dict(run.data.metrics)

            # Parse anvil.experiment_id tag (may be missing for very old runs)
            exp_id_str = tags.get("anvil.experiment_id", "")
            try:
                exp_id = int(exp_id_str)
            except (ValueError, TypeError):
                exp_id = None

            result.append({
                "id": exp_id,
                "status": run.info.status or "RUNNING",
                "run_name": run.data.tags.get("mlflow.runName", "") or "",
                "final_loss": metrics.get("final_loss"),
                "mlflow_run_id": run.info.run_id,
                "dataset_name": tags.get("anvil.dataset.name") or params.get("dataset_id"),
                "dataset_id": params.get("dataset_id"),
                "corpus_id": params.get("corpus_id"),
                "input_digest": tags.get("anvil.input_digest"),
                "input_role": tags.get("anvil.input_role") or "training",
                "engine_backend": params.get("engine_backend", ""),
                "device": params.get("device", ""),
                "created_at": str(run.info.start_time) if run.info.start_time else "",
                "config_id": None,
                "artifact_available": False,  # Caller can set this after checking
            })
        return result

    async def get_experiment(
        self,
        experiment_id: int,
    ) -> dict | None:
        """Find an MLflow run by its anvil.experiment_id tag.

        Returns the same dict shape as list_experiments, plus extra detail fields,
        or None if not found.
        """
        if self._degraded:
            return None
        loop = asyncio.get_event_loop()
        try:
            client = await loop.run_in_executor(None, lambda: self._lazy_init())
            if client is None or not self._experiment_id:
                return None
        except Exception:
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
        except Exception:
            return None

        if not runs:
            return None

        run = runs[0]
        tags = dict(run.data.tags)
        params = dict(run.data.params)
        metrics = dict(run.data.metrics)

        return {
            "id": experiment_id,
            "status": run.info.status or "RUNNING",
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

    async def list_registered_models(self, search: str | None = None) -> list[dict]:
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
        if self._degraded:
            return []
        loop = asyncio.get_event_loop()
        try:
            client = await loop.run_in_executor(None, lambda: self._lazy_init())
            if client is None:
                return []
        except Exception:
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
        except Exception:
            return []

        result = []
        for rm in registered_models:
            try:
                latest_versions = await loop.run_in_executor(
                    None,
                    lambda name=rm.name: client.get_latest_versions(name),
                )
                if not latest_versions:
                    continue
                latest = latest_versions[0]

                # Get run data for final_loss
                final_loss = None
                try:
                    run = await loop.run_in_executor(
                        None, lambda rid=latest.run_id: client.get_run(rid)
                    )
                    if run and run.data and run.data.metrics:
                        final_loss = run.data.metrics.get("final_loss")
                except Exception:
                    pass

                # Local experiment ID lookup removed — all tracking via MLflow now
                experiment_id = None

                # Count total versions
                all_versions = await loop.run_in_executor(
                    None,
                    lambda name=rm.name: client.search_model_versions(f"name='{rm.name}'"),
                )
                total_versions = len(list(all_versions)) if all_versions else 0

                result.append({
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
                        if hasattr(latest, "creation_timestamp") and latest.creation_timestamp
                        else None
                    ),
                    "total_versions": total_versions,
                })
            except Exception:
                continue

        return result


def _create_dataset_sync(name: str, tags: dict | None) -> Any:
    from mlflow.genai.datasets import create_dataset

    return create_dataset(name=name, tags=tags or {})


def _append_records_sync(name: str, records: list[dict]) -> int:
    from mlflow.genai.datasets import get_dataset

    ds = get_dataset(name=name)
    if ds is None:
        raise ValueError(f"Dataset '{name}' not found")
    ds.merge_records(records)
    return len(records)


def _get_dataset_sync(name: str) -> Any | None:
    from mlflow.genai.datasets import get_dataset

    try:
        return get_dataset(name=name)
    except Exception:
        return None
