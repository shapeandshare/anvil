# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Application configuration from environment variables.

Reads configuration values from the environment and ``.env`` file.
Exposes ``get_config()`` as the primary API — a cached callable that
returns a flat dictionary of resolved settings.

When ``ANVIL_WORKSPACE_DIR`` is set, path defaults are overlaid from
``WorkspacePaths`` derived from the workspace root (feature-028).
Environment-variable overrides always take highest precedence.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv
from starlette.requests import Request

from .workspace.workspace_paths import WorkspacePaths

load_dotenv()

# Optional override for the MLflow tracking URI used by the internal
# Python client. Set to None by default; can be set programmatically
# if the default config value is not reachable.
_resolved_mlflow_uri: str | None = None


def set_resolved_mlflow_uri(uri: str) -> None:
    """Override the MLflow tracking URI for internal client connections.

    Called by the supervisor after the MLflow server is started to
    ensure the internal Python client connects to the correct URI.

    Parameters
    ----------
    uri : str
        The full MLflow tracking URI (e.g. ``http://127.0.0.1:5001``).
    """
    global _resolved_mlflow_uri  # pylint: disable=global-statement
    _resolved_mlflow_uri = uri


def get_mlflow_uri() -> str:
    """Return the MLflow tracking URI for internal Python client use.

    Returns the supervisor-resolved URI if set, otherwise falls back
    to the static config value from ``get_config()["mlflow_uri"]``.

    Returns
    -------
    str
        The MLflow tracking server URI.
    """
    if _resolved_mlflow_uri is not None:
        return _resolved_mlflow_uri
    uri: str = get_config()["mlflow_uri"]
    return uri


def get_mlflow_browser_uri(request: Request) -> str:
    """Return the MLflow base URL for browser-facing links.

    Derives the hostname from the incoming HTTP request's ``Host``
    header so links always resolve relative to how the user reached
    the web UI. For example, if the user accesses the app at
    ``http://192.168.1.10:8080``, MLflow links will point to
    ``http://192.168.1.10:5001``.

    Parameters
    ----------
    request : Request
        The incoming Starlette / FastAPI request object.

    Returns
    -------
    str
        A fully qualified MLflow base URL for use in browser-facing
        ``<a>`` tags and redirects.
    """
    host = request.headers.get("host", "127.0.0.1")
    # Strip port from host header (e.g. "192.168.1.10:8080" -> "192.168.1.10")
    hostname = host.split(":")[0]
    mlflow_port = get_config()["mlflow_port"]
    return f"http://{hostname}:{mlflow_port}"


def _parse_port_from_uri(uri: str) -> int:
    """Extract the port number from an MLflow URI. ..."""
    try:
        parsed = urlparse(uri)
        return parsed.port or 5001
    except (ValueError, TypeError):
        return 5001


def _workspace_paths() -> WorkspacePaths | None:
    """Return a ``WorkspacePaths`` instance if ``ANVIL_WORKSPACE_DIR`` is set.

    Returns ``None`` when no workspace is configured (the default
    single-instance boot path).

    The import is deferred to avoid circular imports during package
    initialisation.
    """
    ws = os.getenv("ANVIL_WORKSPACE_DIR")
    if not ws:
        return None
    # import-placement:allow
    # cycle: config -> workspace_paths -> config (circular import during init)
    from .workspace.workspace_paths import WorkspacePaths

    return WorkspacePaths(Path(ws).resolve())


@lru_cache
def get_config() -> dict[str, Any]:
    """Return a cached dictionary of resolved application settings.

    Reads environmnent variables (with ``.env`` support via
    ``python-dotenv``) and returns a flat dictionary. The result is
    cached via ``@lru_cache`` so repeated calls are cheap.

    Keys returned
    -------------
    port : int
        Web server port (default: ``8080``).
    state_db_path : str
        Resolved path to ``anvil-state.db``.
    log_dir : str
        Directory for log files (default: ``logs``).
    mlflow_uri : str
        MLflow tracking server URI.
    mlflow_port : int
        Port parsed from ``mlflow_uri``.
    mlflow_backend_store_uri : str
        SQLite URI for MLflow's backend store.
    mlflow_disable_local : bool
        If ``True``, do not start a local MLflow server.
    db_auto_migrate : bool
        If ``True``, auto-migrate DB schema on startup.
    storage_backend : str
        Storage backend name (default: ``local``).
    device : str
        Device override string (may be empty for auto-detection).

    Returns
    -------
    dict
        Flat dictionary of resolved configuration values.
    """
    default_mlflow_uri = os.getenv("ANVIL_MLFLOW_URI", "http://127.0.0.1:5001")
    mlflow_disable_local = os.getenv("ANVIL_MLFLOW_DISABLE_LOCAL", "").lower() in (
        "true",
        "1",
        "yes",
    )

    state_db_path = os.getenv("ANVIL_STATE_DB_PATH") or str(
        Path("data/anvil-state.db").resolve()
    )

    # ── Workspace-driven path defaults ──────────────────────────────
    # When ANVIL_WORKSPACE_DIR is set, the boot file (instance.json)
    # and WorkspacePaths provide per-instance path defaults.
    # Environment-variable overrides take highest precedence.
    wp = _workspace_paths()
    _ws_state_db = str(wp.state_db_path) if wp else state_db_path
    _ws_log_dir = str(wp.log_dir) if wp else "logs"
    _ws_backup_dir = str(wp.backup_dir) if wp else str(Path("data/backups"))
    _ws_content_dir = str(wp.content_dir) if wp else "data/content"
    _ws_mlflow_backend = (
        wp.mlflow_backend_store_uri
        if wp
        else "sqlite:///" + str(Path("mlruns/mlflow.db").resolve())
    )

    return {
        "port": int(os.getenv("ANVIL_PORT", "8080")),
        "state_db_path": os.getenv("ANVIL_STATE_DB_PATH") or _ws_state_db,
        "log_dir": os.getenv("ANVIL_LOG_DIR", _ws_log_dir),
        "mlflow_uri": default_mlflow_uri,
        "mlflow_port": _parse_port_from_uri(default_mlflow_uri),
        "mlflow_backend_store_uri": _ws_mlflow_backend,
        "mlflow_disable_local": mlflow_disable_local,
        "db_auto_migrate": os.getenv("ANVIL_DB_AUTO_MIGRATE", "true").lower()
        in ("true", "1", "yes"),
        "storage_backend": os.getenv("ANVIL_STORAGE_BACKEND", "local"),
        "device": os.getenv("ANVIL_DEVICE", ""),
        "content_dir": os.getenv("ANVIL_CONTENT_DIR", _ws_content_dir),
        "backup_dir": os.getenv("ANVIL_BACKUP_DIR", _ws_backup_dir),
        "backup_quota_bytes": int(
            os.getenv("ANVIL_BACKUP_QUOTA_BYTES", str(10 * 1024**3))
        ),
        "backup_quota_warn_fraction": float(
            os.getenv("ANVIL_BACKUP_QUOTA_WARN", "0.8")
        ),
        "backup_retention_max_count": (
            int(v) if (v := os.getenv("ANVIL_BACKUP_RETENTION_MAX_COUNT")) else None
        ),
        "backup_retention_max_age_days": (
            int(v) if (v := os.getenv("ANVIL_BACKUP_RETENTION_MAX_AGE_DAYS")) else None
        ),
        "workspace_root": str(wp.root) if wp else "",
    }
