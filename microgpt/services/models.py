from __future__ import annotations

import json
import shutil
from pathlib import Path

from microgpt.db.models.registry import ModelVersion, RegisteredModel
from microgpt.db.repositories.models import ModelRepository

REGISTRY_BASE = Path("data/models/registry")


class ModelRegistryService:
    def __init__(self, repo: ModelRepository):
        self._repo = repo

    async def register_model(
        self,
        experiment_id: int,
        name: str,
        description: str | None = None,
        artifact_source_path: str | None = None,
        final_loss: float | None = None,
        dataset_name: str | None = None,
        hyperparameters: dict | None = None,
    ) -> dict:
        """DEPRECATED: Local model registry write path. New registrations go through
        TrackingService.register_source_model() targeting the MLflow model registry.
        Retained for read-only backward compatibility only."""
        existing = await self._repo.get_by_name(name)
        if existing is None:
            model = RegisteredModel(name=name, description=description)
            model = await self._repo.add(model)
            model_id = model.id
            version_num = 1
        else:
            model_id = existing.id
            version_num = await self._repo.get_next_version_number(model_id)

        artifact_path = self._copy_artifact(name, version_num, artifact_source_path)

        version = ModelVersion(
            model_id=model_id,
            version=version_num,
            experiment_id=experiment_id,
            dataset_name=dataset_name,
            artifact_path=str(artifact_path),
            final_loss=final_loss,
            hyperparameters_json=(
                json.dumps(hyperparameters) if hyperparameters else None
            ),
        )
        version = await self._repo.add_version(version)

        return {
            "id": model_id,
            "name": name,
            "version": version_num,
            "experiment_id": experiment_id,
            "artifact_path": str(artifact_path),
            "final_loss": final_loss,
            "dataset_name": dataset_name,
            "created_at": str(version.created_at),
        }

    def _copy_artifact(
        self,
        name: str,
        version: int,
        source_path: str | None,
    ) -> Path:
        dest_dir = REGISTRY_BASE / name / f"v{version}"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / "model.json"

        if source_path and Path(source_path).exists():
            shutil.copy2(source_path, dest_path)

        return dest_path

    async def list_models(self, search: str | None = None) -> list[dict]:
        models = await self._repo.get_all(search=search)
        result = []
        for m in models:
            versions = await self._repo.get_versions(m.id)
            latest = versions[0] if versions else None
            result.append(
                {
                    "id": m.id,
                    "name": m.name,
                    "description": m.description,
                    "latest_version": latest.version if latest else 0,
                    "total_versions": len(versions),
                    "latest_loss": latest.final_loss if latest else None,
                    "created_at": str(m.created_at),
                }
            )
        return result

    async def get_model(self, model_id: int) -> dict | None:
        model = await self._repo.get_model_with_versions(model_id)
        if model is None:
            return None
        return {
            "id": model.id,
            "name": model.name,
            "description": model.description,
            "versions": [
                {
                    "version": v.version,
                    "experiment_id": v.experiment_id,
                    "dataset_name": v.dataset_name,
                    "final_loss": v.final_loss,
                    "hyperparameters": (
                        json.loads(v.hyperparameters_json)
                        if v.hyperparameters_json
                        else None
                    ),
                    "created_at": str(v.created_at),
                }
                for v in sorted(model.versions, key=lambda x: x.version, reverse=True)
            ],
            "created_at": str(model.created_at),
        }

    async def get_version(self, model_id: int, version: int) -> dict | None:
        model = await self._repo.get(model_id)
        if model is None:
            return None
        v = await self._repo.get_version(model_id, version)
        if v is None:
            return None
        return {
            "version": v.version,
            "experiment_id": v.experiment_id,
            "dataset_name": v.dataset_name,
            "final_loss": v.final_loss,
            "hyperparameters": (
                json.loads(v.hyperparameters_json) if v.hyperparameters_json else None
            ),
            "artifact_path": v.artifact_path,
            "created_at": str(v.created_at),
        }

    async def delete_model(self, model_id: int) -> str | None:
        model = await self._repo.get(model_id)
        if model is None:
            return None
        name = model.name
        await self._repo.delete(model_id)
        model_dir = REGISTRY_BASE / name
        if model_dir.exists():
            shutil.rmtree(model_dir)
        return name

    async def delete_version(self, model_id: int, version: int) -> str | None:
        model = await self._repo.get(model_id)
        if model is None:
            return None
        name = model.name
        v = await self._repo.get_version(model_id, version)
        if v is None:
            return None
        await self._repo.delete_version(model_id, version)
        version_dir = REGISTRY_BASE / name / f"v{version}"
        if version_dir.exists():
            shutil.rmtree(version_dir)
        return name

    async def get_inference_models(self) -> list[dict]:
        models = await self._repo.get_all()
        result = []
        for m in models:
            versions = await self._repo.get_versions(m.id)
            if not versions:
                continue
            latest = versions[0]
            result.append(
                {
                    "id": m.id,
                    "name": m.name,
                    "version": latest.version,
                    "experiment_id": latest.experiment_id,
                    "final_loss": latest.final_loss,
                    "created_at": str(latest.created_at),
                }
            )
        return result

    async def migrate_local_registry_to_mlflow(self, tracking_svc) -> dict:
        from microgpt.db.repositories.experiments import ExperimentRepository

        models = await self._repo.get_all()
        migrated, skipped, failed = 0, 0, 0
        for model in models:
            versions = await self._repo.get_versions(model.id)
            for version in versions:
                if version.experiment_id:
                    exp_repo = ExperimentRepository(self._repo._session)
                    exp = await exp_repo.get(version.experiment_id)
                    if exp and exp.mlflow_run_id:
                        try:
                            await tracking_svc.register_source_model(
                                run_id=exp.mlflow_run_id,
                                dataset_id=exp.dataset_id,
                                corpus_id=getattr(exp, "corpus_id", None),
                                artifact_path="model.json",
                            )
                            migrated += 1
                        except Exception:
                            failed += 1
                    else:
                        skipped += 1
                else:
                    skipped += 1
        return {"migrated": migrated, "skipped": skipped, "failed": failed}
