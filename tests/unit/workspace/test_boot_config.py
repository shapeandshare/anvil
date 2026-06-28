# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for BootConfig load/validate/write."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from anvil.workspace.boot_config import BootConfig


def _valid_data(tmp_path: Path) -> dict[str, Any]:
    """Return a valid BootConfig data dict rooted under *tmp_path*."""
    ws = str(tmp_path / "test-workspace")
    return {
        "name": "test-instance",
        "workspace_root": ws,
        "web_port": 8211,
        "mlflow_port": 8212,
        "state_db_path": f"{ws}/data/anvil-state.db",
    }


def test_valid_config(tmp_path: Path) -> None:
    cfg = BootConfig(**_valid_data(tmp_path))
    assert cfg.name == "test-instance"
    assert cfg.web_port == 8211


def test_missing_required_field(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        partial: dict[str, Any] = {
            "name": "x",
            "workspace_root": str(tmp_path / "x"),
            "web_port": 1,
        }
        BootConfig(**partial)


def test_port_range_negative(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        BootConfig(**{**_valid_data(tmp_path), "web_port": -1})


def test_port_range_high(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        BootConfig(**{**_valid_data(tmp_path), "web_port": 99999})


def test_schema_increments(tmp_path: Path) -> None:
    cfg = BootConfig(**_valid_data(tmp_path))
    assert cfg.config_schema >= 1


def test_roundtrip_to_json(tmp_path: Path) -> None:
    cfg = BootConfig(**_valid_data(tmp_path))
    path = tmp_path / "instance.json"
    cfg.write(path)
    assert path.exists()
    raw = json.loads(path.read_text())
    assert raw["name"] == "test-instance"
    assert raw["web_port"] == 8211


def test_load_from_json(tmp_path: Path) -> None:
    path = tmp_path / "instance.json"
    path.write_text(json.dumps(_valid_data(tmp_path)))
    cfg = BootConfig.load(path)
    assert cfg.name == "test-instance"
    assert cfg.web_port == 8211


def test_load_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "instance.json"
    path.write_text("not json")
    with pytest.raises(ValueError):
        BootConfig.load(path)


def test_workspace_contains_db_path(tmp_path: Path) -> None:
    # state_db_path should be a sensible path within the workspace
    cfg = BootConfig(**_valid_data(tmp_path))
    ws = Path(cfg.workspace_root)
    db = Path(cfg.state_db_path)
    assert str(db).startswith(str(ws)), "DB path must be within workspace root"