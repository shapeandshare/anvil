#!/usr/bin/env python3
"""One-shot migration: copy local SQLite experiment/model data to MLflow.

Idempotent — safe to re-run. Uses --dry-run to preview without changes.

Usage:
    python3 migrations/scripts/migrate_to_mlflow_primary.py [--dry-run]

Behaviour:
  - For each Experiment row with no matching MLflow run, creates a new run
    logging params (from TrainingConfig), metrics (final_loss), and tags.
  - Logs associated Dataset / Corpus inputs to each migrated MLflow run.
  - For each RegisteredModel + ModelVersion, attempts to register the model
    version in the MLflow Model Registry.
  - Generates a summary report. Exits 0 on success, non-zero on error.
"""


import argparse
import asyncio
import sys
from typing import Any

import mlflow.entities
from mlflow.tracking import MlflowClient
from pydantic import BaseModel, Field
from sqlalchemy import Column, Float, ForeignKey, Integer, String, select
from sqlalchemy.orm import Mapped, mapped_column

from ....config import get_config
from ....db.base import Base
from ....db.models.corpus import Corpus
from ....db.models.dataset import Dataset
from ....db.models.registry import ModelVersion, RegisteredModel
from ....db.models.training_config import TrainingConfig
from ....db.session import AsyncSessionLocal
from ....services.mlflow_inputs import MlflowInputResolver

# ---------------------------------------------------------------------------
# Local model: Experiment (table dropped in migration 013 but referenced
# by this one-shot migration script for querying legacy data)
# ---------------------------------------------------------------------------


class Experiment(Base):
    """Local ORM model mapping to the legacy ``experiments`` table.

    The ``experiments`` table was dropped in Alembic migration 013 (see
    ``013_drop_experiment_registry_tables_add_run_id_seq.py``) when the
    project migrated fully to MLflow-based experiment tracking. This
    model exists only so this one-shot migration script can read the
    table if it still exists on a pre-migration database.

    Parameters
    ----------
    **kwargs
        Keyword arguments for column values.
    """

    __tablename__ = "experiments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mlflow_run_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True
    )
    run_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="pending"
    )
    config_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("training_configs.id"), nullable=True
    )
    dataset_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("datasets.id"), nullable=True
    )
    corpus_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    engine_backend: Mapped[str | None] = mapped_column(String(16), nullable=True)
    device: Mapped[str | None] = mapped_column(String(16), nullable=True)
    final_loss: Mapped[float | None] = mapped_column(Float, nullable=True)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


class MigrationReport(BaseModel):
    """Accumulates counts and errors across the migration."""

    experiments_migrated: int = 0
    experiments_skipped: int = 0
    experiments_failed: int = 0
    models_migrated: int = 0
    models_skipped_no_exp: int = 0
    models_skipped_already: int = 0
    models_failed: int = 0
    datasets_logged: int = 0
    corpora_logged: int = 0
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sanitize_model_name(name: str) -> str:
    """MLflow model registry rejects names containing '/' or ':'."""
    return name.replace("/", "-").replace(":", "-")


def _build_params_from_config(
    config: TrainingConfig | None,
) -> list[mlflow.entities.Param]:
    """Build mlflow Param list from a TrainingConfig."""
    params: list[mlflow.entities.Param] = []
    if config is None:
        return params
    param_keys = [
        "n_layer",
        "n_embd",
        "n_head",
        "block_size",
        "num_steps",
        "learning_rate",
        "beta1",
        "beta2",
        "temperature",
        "use_gpu",
    ]
    for key in param_keys:
        v = getattr(config, key, None)
        if v is not None:
            params.append(mlflow.entities.Param(key, str(v)))
    return params


# ---------------------------------------------------------------------------
# Experiment migration
# ---------------------------------------------------------------------------


async def _migrate_experiments(
    client: MlflowClient,
    report: MigrationReport,
    dry_run: bool,
) -> None:
    """Iterate all Experiment rows and ensure matching MLflow runs exist."""
    loop = asyncio.get_event_loop()

    # Resolve or create the "anvil" MLflow experiment
    exp_mlflow = await loop.run_in_executor(
        None, lambda: client.get_experiment_by_name("anvil")
    )
    if exp_mlflow is not None:
        mlflow_experiment_id: str = exp_mlflow.experiment_id
    else:
        mlflow_experiment_id = await loop.run_in_executor(
            None, lambda: client.create_experiment("anvil")
        )

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Experiment).order_by(Experiment.id))
        experiments: list[Experiment] = list(result.scalars().all())

    for exp in experiments:
        # --- Idempotency check: skip if mlflow_run_id already exists ---
        if exp.mlflow_run_id:
            try:
                await loop.run_in_executor(
                    None, lambda rid=exp.mlflow_run_id: client.get_run(rid)
                )
                report.experiments_skipped += 1
                continue
            except Exception:
                # Run not found in MLflow — will create a fresh one
                pass

        if dry_run:
            report.experiments_migrated += 1
            continue

        # --- Load config for params ---
        config: TrainingConfig | None = None
        if exp.config_id:
            async with AsyncSessionLocal() as session:
                config = await session.get(TrainingConfig, exp.config_id)

        try:
            # 1. Create the MLflow run
            mlflow_run = await loop.run_in_executor(
                None,
                lambda exp=exp: client.create_run(
                    mlflow_experiment_id,
                    run_name=exp.run_name or f"experiment-{exp.id}",
                ),
            )
            run_id: str = mlflow_run.info.run_id

            # 2. Log params
            mlflow_params = _build_params_from_config(config)
            if exp.engine_backend:
                mlflow_params.append(
                    mlflow.entities.Param("engine_backend", exp.engine_backend)
                )
            if exp.device:
                mlflow_params.append(mlflow.entities.Param("device", exp.device))
            if mlflow_params:
                await loop.run_in_executor(
                    None,
                    lambda run_id=run_id, mlflow_params=mlflow_params: client.log_batch(
                        run_id=run_id, params=mlflow_params
                    ),
                )

            # 3. Log metrics
            if exp.final_loss is not None:
                await loop.run_in_executor(
                    None,
                    lambda run_id=run_id, exp=exp: client.log_metric(
                        run_id, "final_loss", exp.final_loss
                    ),
                )

            # 4. Set tags
            await loop.run_in_executor(
                None,
                lambda run_id=run_id, exp=exp: client.set_tag(
                    run_id, "anvil.experiment_id", str(exp.id)
                ),
            )
            await loop.run_in_executor(
                None,
                lambda run_id=run_id: client.set_tag(run_id, "anvil.migrated", "true"),
            )

            # 5. Set terminated status if not still running
            status_map = {
                "finished": "FINISHED",
                "failed": "FAILED",
                "running": "RUNNING",
            }
            mlflow_status = status_map.get(exp.status, "RUNNING")
            if mlflow_status != "RUNNING":
                await loop.run_in_executor(
                    None,
                    lambda run_id=run_id, mlflow_status=mlflow_status: client.set_terminated(
                        run_id, status=mlflow_status
                    ),
                )

            # 6. Update local Experiment with mlflow_run_id
            async with AsyncSessionLocal() as session:
                db_exp = await session.get(Experiment, exp.id)
                if db_exp is not None:
                    db_exp.mlflow_run_id = run_id
                    await session.commit()

            # 7. Log dataset input
            if exp.dataset_id:
                try:
                    async with AsyncSessionLocal() as session:
                        resolver = MlflowInputResolver(session)
                        mlflow_ds, _digest = await resolver.resolve_dataset(
                            exp.dataset_id
                        )
                        await loop.run_in_executor(
                            None,
                            lambda run_id=run_id, mlflow_ds=mlflow_ds: client.log_input(
                                run_id, mlflow_ds, context="training"
                            ),
                        )
                    report.datasets_logged += 1
                except Exception as exc:
                    report.warnings.append(
                        f"Experiment {exp.id}: dataset {exp.dataset_id} "
                        f"input logging failed: {exc}"
                    )

            # 8. Log corpus input
            if exp.corpus_id:
                try:
                    async with AsyncSessionLocal() as session:
                        resolver = MlflowInputResolver(session)
                        meta_ds, artifact_paths, _digest = (
                            await resolver.resolve_corpus(exp.corpus_id)
                        )
                        await loop.run_in_executor(
                            None,
                            lambda run_id=run_id, meta_ds=meta_ds: client.log_input(
                                run_id, meta_ds, context="corpus"
                            ),
                        )
                        for artifact_path in artifact_paths:
                            await loop.run_in_executor(
                                None,
                                lambda p=artifact_path, run_id=run_id: client.log_artifact(
                                    run_id, p
                                ),
                            )
                    report.corpora_logged += 1
                except Exception as exc:
                    report.warnings.append(
                        f"Experiment {exp.id}: corpus {exp.corpus_id} "
                        f"input logging failed: {exc}"
                    )

            report.experiments_migrated += 1

        except Exception as exc:
            report.experiments_failed += 1
            report.errors.append(f"Experiment {exp.id}: {exc}")


# ---------------------------------------------------------------------------
# RegisteredModel + ModelVersion migration
# ---------------------------------------------------------------------------


async def _migrate_registered_models(
    client: MlflowClient,
    report: MigrationReport,
    dry_run: bool,
) -> None:
    """Iterate all RegisteredModel + ModelVersion rows and register in MLflow."""
    loop = asyncio.get_event_loop()

    async with AsyncSessionLocal() as session:
        models_result = await session.execute(
            select(RegisteredModel).order_by(RegisteredModel.id)
        )
        registered_models: list[RegisteredModel] = list(models_result.scalars().all())

        versions_result = await session.execute(
            select(ModelVersion).order_by(ModelVersion.id)
        )
        all_versions: list[ModelVersion] = list(versions_result.scalars().all())

    # Group versions by model_id for easier processing
    versions_by_model: dict[int, list[ModelVersion]] = {}
    for mv in all_versions:
        versions_by_model.setdefault(mv.model_id, []).append(mv)

    for rm in registered_models:
        versions = versions_by_model.get(rm.id, [])

        if not versions:
            report.warnings.append(
                f"RegisteredModel '{rm.name}' (id={rm.id}): no versions to migrate"
            )
            continue

        registry_name = _sanitize_model_name(rm.name or f"model-{rm.id}")

        # Check if model already exists in MLflow registry
        model_exists = False
        try:
            await loop.run_in_executor(
                None,
                lambda registry_name=registry_name: client.get_registered_model(
                    registry_name
                ),
            )
            model_exists = True
        except Exception:
            pass

        for mv in versions:
            # Skip if experiment doesn't exist or has no mlflow_run_id
            if mv.experiment_id is None:
                report.models_skipped_no_exp += 1
                report.warnings.append(
                    f"ModelVersion (id={mv.id}, model='{rm.name}'): "
                    f"no experiment_id — skipping"
                )
                continue

            async with AsyncSessionLocal() as session:
                exp = await session.get(Experiment, mv.experiment_id)

            if exp is None or not exp.mlflow_run_id:
                report.models_skipped_no_exp += 1
                report.warnings.append(
                    f"ModelVersion (id={mv.id}, model='{rm.name}'): "
                    f"experiment {mv.experiment_id} has no MLflow run — skipping"
                )
                continue

            run_id = exp.mlflow_run_id

            # Check if version already exists for this run_id
            if model_exists:
                try:
                    existing_versions = await loop.run_in_executor(
                        None,
                        lambda registry_name=registry_name: client.search_model_versions(
                            f"name='{registry_name}'"
                        ),
                    )
                    already_registered = any(
                        v.run_id == run_id for v in existing_versions
                    )
                    if already_registered:
                        report.models_skipped_already += 1
                        continue
                except Exception:
                    pass

            if dry_run:
                report.models_migrated += 1
                continue

            # Attempt registration
            try:
                # Ensure registered model exists
                if not model_exists:
                    try:
                        await loop.run_in_executor(
                            None,
                            lambda registry_name=registry_name: client.create_registered_model(
                                registry_name
                            ),
                        )
                        model_exists = True
                    except Exception:
                        pass

                source = f"runs:/{run_id}/{mv.artifact_path or ''}"

                await loop.run_in_executor(
                    None,
                    lambda registry_name=registry_name, source=source, run_id=run_id: client.create_model_version(
                        name=registry_name,
                        source=source,
                        run_id=run_id,
                    ),
                )
                report.models_migrated += 1

            except Exception as exc:
                report.models_failed += 1
                report.errors.append(
                    f"ModelVersion (id={mv.id}, model='{rm.name}'): {exc}"
                )


# ---------------------------------------------------------------------------
# Report printing
# ---------------------------------------------------------------------------


def _print_report(report: MigrationReport, dry_run: bool) -> None:
    """Print a formatted migration summary."""
    prefix = "[DRY RUN] " if dry_run else ""

    print(f"\n{prefix}Migration Report")
    print("=" * 50)
    print(
        f"  Experiments:          {report.experiments_migrated} migrated, "
        f"{report.experiments_skipped} skipped, "
        f"{report.experiments_failed} failed"
    )
    print(
        f"  Registered models:    {report.models_migrated} migrated, "
        f"{report.models_skipped_already} skipped (already exist), "
        f"{report.models_skipped_no_exp} skipped (no experiment), "
        f"{report.models_failed} failed"
    )
    print(f"  Dataset inputs logged: {report.datasets_logged}")
    print(f"  Corpus inputs logged:  {report.corpora_logged}")

    if report.warnings:
        print(f"\n  Warnings ({len(report.warnings)}):")
        for w in report.warnings:
            print(f"    ⚠  {w}")

    if report.errors:
        print(f"\n  Errors ({len(report.errors)}):")
        for e in report.errors:
            print(f"    ✗  {e}")

    print("=" * 50)
    total_ok = (
        report.experiments_migrated
        + report.experiments_skipped
        + report.models_migrated
        + report.models_skipped_already
        + report.models_skipped_no_exp
    )
    total_fail = report.experiments_failed + report.models_failed
    print(f"  {total_ok} OK, {total_fail} failed")
    print()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate local SQLite experiment/model data to MLflow.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print report of what would be migrated without making changes.",
    )
    args = parser.parse_args()

    cfg = get_config()
    mlflow_uri: str = cfg["mlflow_uri"]

    client = MlflowClient(tracking_uri=mlflow_uri)

    report = MigrationReport()

    try:
        asyncio.run(_migrate_experiments(client, report, args.dry_run))
        asyncio.run(_migrate_registered_models(client, report, args.dry_run))
    except ConnectionError as exc:
        report.errors.append(f"MLflow server unreachable at {mlflow_uri}: {exc}")
        _print_report(report, args.dry_run)
        sys.exit(2)
    except Exception as exc:
        report.errors.append(f"Unexpected error: {exc}")
        _print_report(report, args.dry_run)
        sys.exit(3)

    _print_report(report, args.dry_run)

    if report.experiments_failed > 0 or report.models_failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
