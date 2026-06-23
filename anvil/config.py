# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Application configuration from environment variables.

Reads configuration values from the environment and ``.env`` file.
Exposes ``get_config()`` as the primary API — a cached callable that
returns a flat dictionary of resolved settings.

Module-level Constants
----------------------
_resolved_mlflow_uri : str or None
    Optional runtime override for the MLflow tracking URI. Set via
    :func:`set_resolved_mlflow_uri` when the supervisor resolves a
    dynamic URI that differs from the static config default.
"""

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from starlette.requests import Request

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
    global _resolved_mlflow_uri
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
    return get_config()["mlflow_uri"]


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
    """Extract the port number from an MLflow URI.

    Handles URIs such as ``http://127.0.0.1:5001`` and returns the
    port component, defaulting to ``5001`` on failure.

    Parameters
    ----------
    uri : str
        A fully qualified URI string.

    Returns
    -------
    int
        The port number extracted from the URI, or ``5001`` as a
        fallback.
    """
    try:
        from urllib.parse import urlparse

        parsed = urlparse(uri)
        return parsed.port or 5001
    except Exception:
        return 5001


@lru_cache
def get_config():
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

    return {
        "port": int(os.getenv("ANVIL_PORT", "8080")),
        "state_db_path": state_db_path,
        "log_dir": os.getenv("ANVIL_LOG_DIR", "logs"),
        "mlflow_uri": default_mlflow_uri,
        "mlflow_port": _parse_port_from_uri(default_mlflow_uri),
        "mlflow_backend_store_uri": "sqlite:///"
        + str(Path("mlruns/mlflow.db").resolve()),
        "mlflow_disable_local": mlflow_disable_local,
        "db_auto_migrate": os.getenv("ANVIL_DB_AUTO_MIGRATE", "true").lower()
        in ("true", "1", "yes"),
        "storage_backend": os.getenv("ANVIL_STORAGE_BACKEND", "local"),
        "device": os.getenv("ANVIL_DEVICE", ""),
        "content_dir": os.getenv("ANVIL_CONTENT_DIR", "data/content"),
        # Backup & Restore (feature 026)
        "backup_dir": os.getenv("ANVIL_BACKUP_DIR", str(Path("data/backups"))),
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
    }
