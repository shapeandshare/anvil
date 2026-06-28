# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for BootConfig load/validate/write."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from anvil.workspace.boot_config import BootConfig

VALID_DATA: dict[str, object] = {
    "name": "test-instance",
    "workspace_root": "/tmp/test-workspace",
    "web_port": 8211,
    "mlflow_port": 8212,
    "state_db_path": "/tmp/test-workspace/data/anvil-state.db",
}


def test_valid_config() -> None:
    cfg = BootConfig(**VALID_DATA)
    assert cfg.name == "test-instance"
    assert cfg.web_port == 8211


def test_missing_required_field() -> None:
    with pytest.raises(ValidationError):
        BootConfig(name="x", workspace_root="/tmp/x", web_port=1)  # missing mlflow_port


def test_port_range_negative() -> None:
    with pytest.raises(ValidationError):
        BootConfig(**{**VALID_DATA, "web_port": -1})


def test_port_range_high() -> None:
    with pytest.raises(ValidationError):
        BootConfig(**{**VALID_DATA, "web_port": 99999})


def test_schema_increments() -> None:
    cfg = BootConfig(**VALID_DATA)
    assert cfg.config_schema >= 1


def test_roundtrip_to_json(tmp_path: Path) -> None:
    cfg = BootConfig(**VALID_DATA)
    path = tmp_path / "instance.json"
    cfg.write(path)
    assert path.exists()
    raw = json.loads(path.read_text())
    assert raw["name"] == "test-instance"
    assert raw["web_port"] == 8211


def test_load_from_json(tmp_path: Path) -> None:
    path = tmp_path / "instance.json"
    path.write_text(json.dumps(VALID_DATA))
    cfg = BootConfig.load(path)
    assert cfg.name == "test-instance"
    assert cfg.web_port == 8211


def test_load_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "instance.json"
    path.write_text("not json")
    with pytest.raises(ValueError):
        BootConfig.load(path)


def test_workspace_contains_db_path() -> None:
    # state_db_path should be a sensible path within the workspace
    cfg = BootConfig(**VALID_DATA)
    ws = Path(cfg.workspace_root)
    db = Path(cfg.state_db_path)
    assert str(db).startswith(str(ws)), "DB path must be within workspace root"


__all__ = [
    "test_valid_config",
    "test_missing_required_field",
    "test_port_range_negative",
    "test_port_range_high",
    "test_schema_increments",
    "test_roundtrip_to_json",
    "test_load_from_json",
    "test_load_invalid_json",
    "test_workspace_contains_db_path",
]
