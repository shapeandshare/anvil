"""Application configuration from environment variables."""

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@lru_cache
def get_config():
    return {
        "port": int(os.getenv("MICROGPT_PORT", "8080")),
        "db_path": os.getenv(
            "MICROGPT_DB_PATH", str(Path("data/microgpt.db").resolve())
        ),
        "log_dir": os.getenv("MICROGPT_LOG_DIR", "logs"),
        "mlflow_uri": os.getenv("MICROGPT_MLFLOW_URI", "sqlite:///./mlruns/mlflow.db"),
        "storage_backend": os.getenv("MICROGPT_STORAGE_BACKEND", "local"),
        "device": os.getenv("MICROGPT_DEVICE", ""),
    }
