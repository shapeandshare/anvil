# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for WorkspacePaths derivation."""

from __future__ import annotations

from pathlib import Path

from anvil.workspace.workspace_paths import WorkspacePaths


def test_every_path_derives_from_root(tmp_path: Path) -> None:
    root = tmp_path / "test-workspace"
    wp = WorkspacePaths(root)
    assert wp.state_db_path == root / "data/anvil-state.db"
    assert wp.datasets_dir == root / "data/datasets"
    assert wp.storage_dir == root / "data/storage"
    assert wp.models_dir == root / "data/models"
    assert wp.content_dir == root / "data/content"
    assert wp.mlruns_dir == root / "mlruns"
    assert wp.api_key_path == root / "data/.api_key"
    assert wp.log_dir == root / "logs"
    assert wp.backup_dir == root / "data/backups"


def test_mlflow_backend_store_uri(tmp_path: Path) -> None:
    root = tmp_path / "test-workspace"
    wp = WorkspacePaths(root)
    expected = f"sqlite:///{root}/mlruns/mlflow.db"
    assert wp.mlflow_backend_store_uri == expected


def test_path_overrides_override_default(tmp_path: Path) -> None:
    root = tmp_path / "test-workspace"
    wp = WorkspacePaths(root, overrides={"models_dir": root / "alt-models"})
    assert wp.models_dir == root / "alt-models"
    # Non-overridden paths still derive from root
    assert wp.datasets_dir == root / "data/datasets"


def test_no_write_outside_root(tmp_path: Path) -> None:
    """Sanity check: no path escapes the workspace root."""
    wp = WorkspacePaths(tmp_path)
    for p in [
        wp.state_db_path,
        wp.datasets_dir,
        wp.storage_dir,
        wp.models_dir,
        wp.content_dir,
        wp.mlruns_dir,
        wp.api_key_path,
        wp.log_dir,
        wp.backup_dir,
    ]:
        rel = Path(p).relative_to(tmp_path)
        assert not rel.as_posix().startswith(".."), f"{p} escapes root"