"""Application configuration from environment variables."""

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Allows the supervisor to override the MLflow URI with an auto-detected
# LAN-accessible address after starting the MLflow server. Set to None
# initially; the supervisor calls set_resolved_mlflow_uri() on startup if
# the user hasn't explicitly configured ANVIL_MLFLOW_URI.
_resolved_mlflow_uri: str | None = None


def set_resolved_mlflow_uri(uri: str) -> None:
    """Override the MLflow tracking URI used for browser-facing links.

    Called by the supervisor after auto-detecting the LAN IP so that
    MLflow URLs served to the web UI resolve correctly from other machines.
    """
    global _resolved_mlflow_uri  # noqa: PLW0603
    _resolved_mlflow_uri = uri


def get_mlflow_uri() -> str:
    """Return the best MLflow tracking URI for browser-facing links.

    Returns the supervisor-resolved (LAN-accessible) URI if set,
    otherwise falls back to the static config value.
    """
    if _resolved_mlflow_uri is not None:
        return _resolved_mlflow_uri
    return get_config()["mlflow_uri"]


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
    return {
        "port": int(os.getenv("ANVIL_PORT", "8080")),
        "db_path": os.getenv(
            "ANVIL_DB_PATH", str(Path("data/anvil.db").resolve())
        ),
        "log_dir": os.getenv("ANVIL_LOG_DIR", "logs"),
        "mlflow_uri": default_mlflow_uri,
        "mlflow_port": _parse_port_from_uri(default_mlflow_uri),
        "mlflow_backend_store_uri": "sqlite:///"
        + str(Path("mlruns/mlflow.db").resolve()),
        "storage_backend": os.getenv("ANVIL_STORAGE_BACKEND", "local"),
        "device": os.getenv("ANVIL_DEVICE", ""),
    }
