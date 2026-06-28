# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Boot-time configuration loaded from a per-workspace ``instance.json`` file.

The boot file is the authoritative persisted source for the four
boot-critical values: ``workspace_root``, ``web_port``, ``mlflow_port``,
and ``state_db_path``.  It is deliberately minimal — per-location path
overrides live in the per-instance ``runtime_config`` table.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field, ValidationInfo, field_validator


class BootConfig(BaseModel):
    """Boot-critical instance configuration persisted in ``instance.json``.

    Parameters
    ----------
    name : str
        Instance name, must be non-empty and filesystem/URL-safe.
    workspace_root : str
        Absolute path to the workspace root directory.
    web_port : int
        Web/uvicorn bind port (1-65535).
    mlflow_port : int
        MLflow sidecar port (1-65535).
    state_db_path : str
        Path to the per-instance SQLite app database.  Should be
        within ``workspace_root``.
    schema : int
        Boot-file format version.  Currently ``1``.
    """

    name: str = Field(min_length=1, pattern=r"^[a-zA-Z0-9_-]+$")
    workspace_root: str
    web_port: int = Field(ge=1, le=65535)
    mlflow_port: int = Field(ge=1, le=65535)
    state_db_path: str = ""
    config_schema: int = Field(default=1, ge=1, alias="schema")

    @field_validator("state_db_path", mode="before")
    @classmethod
    def _default_state_db_path(cls, v: str, info: ValidationInfo) -> str:
        if v:
            return v
        root = info.data.get("workspace_root", ".")
        return str(Path(root) / "data" / "anvil-state.db")

    @field_validator("workspace_root", mode="before")
    @classmethod
    def _resolve_abs(cls, v: str) -> str:
        return str(Path(v).resolve())

    @field_validator("state_db_path", mode="after")
    @classmethod
    def _resolve_db_abs(cls, v: str) -> str:
        return str(Path(v).resolve())

    # ── I/O ───────────────────────────────────────────────────────

    @classmethod
    def load(cls, path: Path) -> BootConfig:
        """Load and validate from a JSON file."""
        return cls.model_validate_json(path.read_text())

    def write(self, path: Path) -> None:
        """Validate and write to a JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2))
