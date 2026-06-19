"""Application configuration from environment variables."""

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
    """Override the MLflow tracking URI used for internal client connections."""
    global _resolved_mlflow_uri
    _resolved_mlflow_uri = uri


def get_mlflow_uri() -> str:
    """Return the MLflow tracking URI for internal Python client use.

    Returns the supervisor-resolved URI if set, otherwise falls back
    to the static config value.
    """
    if _resolved_mlflow_uri is not None:
        return _resolved_mlflow_uri
    return get_config()["mlflow_uri"]


def get_mlflow_browser_uri(request: Request) -> str:
    """Return the MLflow base URL for browser-facing links.

    Derives the hostname from the incoming HTTP request's Host header
    so links always resolve relative to how the user reached the web UI.
    For example, if the user accesses the app at http://192.168.1.10:8080,
    MLflow links will point to http://192.168.1.10:5001.
    """
    host = request.headers.get("host", "127.0.0.1")
    # Strip port from host header (e.g. "192.168.1.10:8080" -> "192.168.1.10")
    hostname = host.split(":")[0]
    mlflow_port = get_config()["mlflow_port"]
    return f"http://{hostname}:{mlflow_port}"


def _parse_port_from_uri(uri: str) -> int:
    """Extract the port number from an MLflow URI like http://127.0.0.1:5001."""
    try:
        from urllib.parse import urlparse

        parsed = urlparse(uri)
        return parsed.port or 5001
    except Exception:
        return 5001


@lru_cache
def get_config():
    default_mlflow_uri = os.getenv(
        "ANVIL_MLFLOW_URI", "http://127.0.0.1:5001"
    )
    mlflow_disable_local = os.getenv(
        "ANVIL_MLFLOW_DISABLE_LOCAL", ""
    ).lower() in ("true", "1", "yes")

    # Deprecation path: ANVIL_DB_PATH → ANVIL_STATE_DB_PATH
    state_db_path = os.getenv("ANVIL_STATE_DB_PATH")
    legacy_db_path = os.getenv("ANVIL_DB_PATH")
    if state_db_path is None and legacy_db_path is not None:
        import logging
        logging.getLogger(__name__).warning(
            "ANVIL_DB_PATH is deprecated. Use ANVIL_STATE_DB_PATH instead."
        )
        state_db_path = legacy_db_path
    if state_db_path is None:
        state_db_path = str(Path("data/anvil-state.db").resolve())

    return {
        "port": int(os.getenv("ANVIL_PORT", "8080")),
        "db_path": state_db_path,
        "state_db_path": state_db_path,
        "log_dir": os.getenv("ANVIL_LOG_DIR", "logs"),
        "mlflow_uri": default_mlflow_uri,
        "mlflow_port": _parse_port_from_uri(default_mlflow_uri),
        "mlflow_backend_store_uri": "sqlite:///"
        + str(Path("mlruns/mlflow.db").resolve()),
        "mlflow_disable_local": mlflow_disable_local,
        "storage_backend": os.getenv("ANVIL_STORAGE_BACKEND", "local"),
        "device": os.getenv("ANVIL_DEVICE", ""),
    }
