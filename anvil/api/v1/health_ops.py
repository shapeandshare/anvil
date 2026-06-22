# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Health check and service management routes for the v1 API.

Provides system health monitoring and lifecycle management for
background services (web, MLflow). Extracted from ``router.py``
as part of structural decomposition.
"""

import asyncio
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Annotated

import psutil
from fastapi import APIRouter, Depends, HTTPException, Request

from anvil import __version__ as anvil_version
from anvil.api.deps import get_workbench
from anvil.config import get_config, get_mlflow_browser_uri
from anvil.gpu import detect_gpu
from anvil.workbench import AnvilWorkbench

router = APIRouter()

_start_time: float = time.time()
"""float: Unix timestamp (epoch seconds) when the server process started."""

_bootstrap_lock: asyncio.Lock = asyncio.Lock()
"""asyncio.Lock: Serializes concurrent bootstrap operations."""
_bootstrap_in_progress: bool = False
"""bool: True while a bootstrap is actively running — drives HTTP 409."""


@router.post("/demo/bootstrap")
async def rebootstrap_demo(
    workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> dict:
    """Re-bootstrap all demo data into the database.

    Idempotent — existing entities are skipped, not duplicated.
    Protected by a server-side ``asyncio.Lock`` that returns
    HTTP 409 if a bootstrap is already in progress.

    Parameters
    ----------
    workbench : AnvilWorkbench
        Session-bound workbench injected via FastAPI dependency.

    Returns
    -------
    dict
        BootstrapResult fields (corpora_created, datasets_created,
        corpora_skipped, datasets_skipped, errors, total_time_ms).
    """
    global _bootstrap_in_progress
    if _bootstrap_in_progress:
        raise HTTPException(
            status_code=409,
            detail={"status": "busy", "message": "Bootstrap already in progress"},
        )
    _bootstrap_in_progress = True
    try:
        async with _bootstrap_lock:
            result = await workbench.demo.bootstrap_all()
            return result.model_dump()
    finally:
        _bootstrap_in_progress = False


@router.get("/health")
async def health():
    """Return a bare liveness health check.

    This endpoint is auth-exempt (for Docker compose healthcheck).
    Detailed system metrics (version, uptime, CPU, memory, disk, GPU)
    are available at the authenticated ``GET /v1/health/detailed``
    endpoint (FR-021).

    Returns
    -------
    dict
        ``{"status": "healthy"}``
    """
    return {"status": "healthy"}


@router.get("/health/detailed")
async def health_detailed():
    """Return detailed system health metrics.

    Provides version, uptime, CPU, memory, disk, and GPU information.
    This endpoint requires authentication (unlike the bare
    ``GET /v1/health`` liveness check).

    Returns
    -------
    dict
        ``status``, ``version``, ``uptime_seconds``, ``system`` metrics and
        ``gpu`` details.
    """
    cpu_percent = psutil.cpu_percent(interval=0)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    gpu = detect_gpu()
    return {
        "status": "healthy",
        "version": anvil_version,
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
            "memory_total_gb": gpu.memory_total_gb,
            "memory_available_gb": gpu.memory_available_gb,
            "compute_capability": gpu.compute_capability,
            "torch_version": gpu.torch_version,
            "cuda_version": gpu.cuda_version,
            "errors": gpu.errors,
        },
    }


@router.get("/services")
async def list_services(request: Request):
    """List available services and their status.

    Parameters
    ----------
    request : Request
        The incoming HTTP request.

    Returns
    -------
    dict
        List of service dicts with ``name``, ``status``, ``port``, and
        ``mlflow_url`` where applicable.
    """
    mlflow = getattr(request.app.state, "mlflow", None)
    if mlflow is None:
        mlflow_status = (
            "external" if get_config()["mlflow_disable_local"] else "stopped"
        )
    else:
        mlflow_status = "running" if mlflow.is_running else "stopped"
    return {
        "services": [
            {"name": "web", "status": "running"},
            {
                "name": "mlflow",
                "status": mlflow_status,
                "port": get_config()["mlflow_port"],
                "mlflow_url": get_mlflow_browser_uri(request),
            },
        ]
    }


_ALLOWED_SERVICE_NAMES: frozenset[str] = frozenset({"web", "mlflow"})
"""Set of allowed service name values for log and management endpoints."""


def _validate_service_name(name: str) -> str:
    """Validate and return a safe log-file stem for a service name.

    Strips directory components (defense-in-depth) and checks against the
    allowlist. Returns the basename so callers can safely construct paths.

    Parameters
    ----------
    name : str
        Service name to validate.

    Returns
    -------
    str
        The safe basename (e.g. ``"web"`` or ``"mlflow"``).

    Raises
    ------
    HTTPException
        If the name is unknown or contains path traversal characters.
    """
    safe = os.path.basename(name)
    if safe != name or "/" in name or "\\" in name or ".." in name:
        raise HTTPException(status_code=400, detail=f"Invalid service name: {name}")
    if safe not in _ALLOWED_SERVICE_NAMES:
        raise HTTPException(status_code=404, detail=f"Unknown service: {name}")
    return safe


@router.get("/services/logs/{name}")
async def get_service_logs(name: str, lines: int = 50):
    """Retrieve the last N lines of a service log file.

    Parameters
    ----------
    name : str
        Service name (e.g. ``"web"``, ``"mlflow"``).
    lines : int, optional
        Number of log lines to return. Defaults to ``50``.

    Returns
    -------
    dict
        ``logs`` list of log line strings.
    """
    safe_name = _validate_service_name(name)
    log_file = Path("logs") / f"{safe_name}.log"
    if not log_file.exists():
        return {"logs": []}
    content = log_file.read_text().splitlines()
    return {"logs": content[-lines:]}


@router.post("/services/restart-all")
async def restart_all_services(request: Request):
    """Restart all managed services (MLflow).

    Parameters
    ----------
    request : Request
        The incoming HTTP request.

    Returns
    -------
    dict
        Status and per-service restart results.
    """
    results = {}
    mlflow = getattr(request.app.state, "mlflow", None)
    if mlflow is not None:
        if mlflow.is_running:
            mlflow.stop()
        mlflow.start()
        results["mlflow"] = "restarted"
    else:
        results["mlflow"] = "not_initialized"
    results["web"] = "cannot_manage"
    return {"status": "ok", "results": results}


@router.post("/services/logs/{name}/clear")
async def clear_service_logs(name: str):
    """Clear a service's log file by truncating it.

    Parameters
    ----------
    name : str
        Service name.

    Returns
    -------
    dict
        ``status`` set to ``"cleared"`` or ``"no_logs"``.
    """
    safe_name = _validate_service_name(name)
    log_file = Path("logs") / f"{safe_name}.log"
    if log_file.exists():
        log_file.write_text("")
        return {"status": "cleared"}
    return {"status": "no_logs"}


@router.post("/services/{name}/start")
async def start_service(name: str, request: Request):
    """Start a named service.

    Parameters
    ----------
    name : str
        Service name (``"mlflow"``).
    request : Request
        The incoming HTTP request.

    Returns
    -------
    dict
        Status and details about the started service.
    """
    if name == "mlflow":
        mlflow = getattr(request.app.state, "mlflow", None)
        if mlflow is None:
            raise HTTPException(status_code=400, detail="MLflow not initialized")
        if not mlflow.is_running:
            mlflow.start()
        return {
            "status": "started",
            "name": "mlflow",
            "port": get_config()["mlflow_port"],
        }
    raise HTTPException(status_code=404, detail=f"Unknown service: {name}")


@router.post("/services/{name}/stop")
async def stop_service(name: str, request: Request):
    """Stop a named service.

    Parameters
    ----------
    name : str
        Service name (``"mlflow"``).
    request : Request
        The incoming HTTP request.

    Returns
    -------
    dict
        Status of the stop operation.
    """
    if name == "mlflow":
        mlflow = getattr(request.app.state, "mlflow", None)
        if mlflow is None:
            raise HTTPException(status_code=400, detail="MLflow not initialized")
        if mlflow.is_running:
            mlflow.stop()
        return {"status": "stopped", "name": "mlflow"}
    raise HTTPException(status_code=404, detail=f"Unknown service: {name}")


@router.post("/services/{name}/restart")
async def restart_service(name: str, request: Request):
    """Restart a named service.

    Parameters
    ----------
    name : str
        Service name (``"mlflow"``).
    request : Request
        The incoming HTTP request.

    Returns
    -------
    dict
        Status of the restart operation.
    """
    if name == "mlflow":
        mlflow = getattr(request.app.state, "mlflow", None)
        if mlflow is None:
            raise HTTPException(status_code=400, detail="MLflow not initialized")
        if mlflow.is_running:
            mlflow.stop()
        mlflow.start()
        return {"status": "restarted", "name": "mlflow"}
    raise HTTPException(status_code=404, detail=f"Unknown service: {name}")


def _poll_port(port: int, timeout: float = 2.0) -> list[int]:
    """Poll for processes listening on a given port.

    Parameters
    ----------
    port : int
        Port number to scan.
    timeout : float
        Maximum wait time in seconds. Defaults to ``2.0``.

    Returns
    -------
    list of int
        PID(s) of processes using the port.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return [int(pid) for pid in result.stdout.strip().split()]
        time.sleep(0.5)
    return []


@router.post("/services/{name}/kill-port")
async def kill_service_port(name: str, request: Request):
    """Kill any process occupying a service's port.

    Parameters
    ----------
    name : str
        Service name (``"mlflow"``).
    request : Request
        The incoming HTTP request.

    Returns
    -------
    dict
        Status of the port-kill operation.

    Raises
    ------
    HTTPException
        If the service is unknown or port scanning fails.
    """
    if name == "mlflow":
        port = get_config()["mlflow_port"]
    else:
        raise HTTPException(status_code=404, detail=f"Unknown service: {name}")
    pids = _poll_port(port)
    killed = []
    for pid in pids:
        try:
            os.kill(pid, signal.SIGKILL)
            killed.append(pid)
        except ProcessLookupError:
            pass
    return {"status": "killed", "port": port, "killed": killed}
