# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Shared environment snapshot helper for health and about endpoints.

Provides ``_collect_environment_snapshot()`` which gathers system
metrics (CPU, memory, disk, GPU), database health, MLflow reachability,
tracking status, git commit hash, Python version, and asset counts
into a single dict.  This helper is consumed by both
``GET /v1/health/detailed`` and ``GET /v1/about``, eliminating
duplicated psutil/gpu/db/mlflow-probing code.
"""

from __future__ import annotations

import platform
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

import psutil

from ...config import get_config
from ...db.migration import MigrationService
from ...db.schema_version import SCHEMA_VERSION
from ...gpu import detect_gpu
from ...workbench import AnvilWorkbench

_start_time: float = time.time()
"""float: Unix timestamp (epoch seconds) when the server process started."""


def _get_git_commit_hash() -> str:
    """Return the short git commit hash of the repository.

    Runs ``git rev-parse --short HEAD`` from the repository root.
    If the command fails (e.g. running from a pip-installed wheel
    with no ``.git`` directory), returns ``"unknown"``.

    Returns
    -------
    str
        Short SHA (e.g. ``"a1b2c3d"``) or ``"unknown"``.
    """
    # Resolve repo root: anvil/api/v1/_environment.py → anvil/ → repo root
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        return result.stdout.strip()
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return "unknown"


async def _collect_environment_snapshot(
    workbench: AnvilWorkbench,
) -> dict[str, Any]:
    """Collect system, GPU, database, MLflow, tracking, and asset stats.

    This is the shared helper used by both the health/detailed endpoint
    and the about page.  It gathers all environment metrics in a single
    async call to avoid duplicated probing logic.

    Parameters
    ----------
    workbench : AnvilWorkbench
        Session-bound workbench injected via FastAPI dependency.

    Returns
    -------
    dict
        Environment snapshot with keys ``uptime_seconds``, ``system``,
        ``gpu``, ``database``, ``mlflow``, ``tracking``,
        ``commit_hash``, ``python_version``, and ``asset_counts``.
    """
    cpu_percent = psutil.cpu_percent(interval=0)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    gpu = detect_gpu()

    # Database health
    db_status = "unknown"
    db_schema_version = 0
    db_migration = "unknown"
    try:
        svc = MigrationService()
        db_schema_version = await svc.get_schema_version()
        db_migration = (await svc.current()) or "unknown"
        db_status = "connected"
    except (RuntimeError, ValueError, OSError):
        db_status = "error"

    # MLflow health
    mlflow_status = "unknown"
    try:
        sock = socket.create_connection(
            ("127.0.0.1", get_config()["mlflow_port"]), timeout=3
        )
        sock.close()
        mlflow_status = "reachable"
    except OSError:
        mlflow_status = "unreachable"

    # Asset counts
    datasets = len(await workbench.dataset_repo.get_all())
    corpora = len(await workbench.corpus_repo.get_all())
    external_models = len(await workbench.external_model_repo.get_all())
    training_runs = workbench.training_runs.run_count

    return {
        "uptime_seconds": int(time.time() - _start_time),
        "system": {
            "cpu_percent": cpu_percent,
            "memory_percent": mem.percent,
            "memory_used_gb": round(mem.used / (1024**3), 1),
            "memory_total_gb": round(mem.total / (1024**3), 1),
            "disk_percent": disk.percent,
            "disk_used_gb": round(disk.used / (1024**3), 1),
            "disk_total_gb": round(disk.total / (1024**3), 1),
        },
        "gpu": {
            "available": gpu.available,
            "backend": gpu.backend,
            "device_name": gpu.device_name,
            "memory_total_gb": (
                gpu.memory_total_gb if gpu.memory_total_gb is not None else 0.0
            ),
            "memory_available_gb": (
                gpu.memory_available_gb if gpu.memory_available_gb is not None else 0.0
            ),
            "compute_capability": gpu.compute_capability,
            "torch_version": gpu.torch_version,
            "cuda_version": gpu.cuda_version,
        },
        "database": {
            "status": db_status,
            "schema_version": db_schema_version,
            "expected_schema_version": SCHEMA_VERSION,
            "migration_revision": db_migration,
        },
        "mlflow": {
            "status": mlflow_status,
        },
        "tracking": workbench.tracking.tracking_status.model_dump(),
        "commit_hash": _get_git_commit_hash(),
        "python_version": platform.python_version(),
        "asset_counts": {
            "datasets": datasets,
            "corpora": corpora,
            "external_models": external_models,
            "training_runs": training_runs,
        },
    }
