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
        try:
            from datetime import UTC, datetime

            from anvil.db.repositories.experiments import ExperimentRepository
            from anvil.db.session import AsyncSessionLocal

            async with AsyncSessionLocal() as session:
                repo = ExperimentRepository(session)
                orphaned = await repo.find_orphaned()
                for exp in orphaned:
                    await repo.mark_failed(
                        experiment_id=exp.id,
                        error_message="interrupted/terminated",
                        completed_at=datetime.now(UTC),
                    )
                await session.commit()
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
            registry_name = name
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
