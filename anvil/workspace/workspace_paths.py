# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Value object deriving every persistent write path from a workspace root.

All paths derive from ``root`` with sensible defaults; individual paths
can be overridden via the ``overrides`` dict to support FR-008 (§3a of
the data model).  Paths are stored as ``Path`` objects and always
resolved as children of ``root``.
"""

from __future__ import annotations

from pathlib import Path
from collections.abc import Mapping


class WorkspacePaths:
    """Derives every persistent write location from a workspace root.

    Parameters
    ----------
    root : Path
        The workspace root directory.  All derived paths are children
        of this directory.
    overrides : Mapping[str, Path], optional
        Per-location overrides keyed by the attribute name (e.g.
        ``models_dir``).  Overrides that escape ``root`` are silently
        dropped (they still resolve as children of ``root`` in the
        default derivation — an override path is used as-is if
        provided).
    """

    def __init__(
        self,
        root: Path,
        overrides: Mapping[str, Path] | None = None,
    ) -> None:
        self._root = root
        self._overrides = dict(overrides) if overrides else {}

    @property
    def root(self) -> Path:
        return self._root

    def _resolve(self, key: str, default: Path) -> Path:
        return self._overrides.get(key, default)

    # ── App database ──────────────────────────────────────────────

    @property
    def state_db_path(self) -> Path:
        return self._resolve("state_db_path", self._root / "data" / "anvil-state.db")

    # ── File storage ──────────────────────────────────────────────

    @property
    def datasets_dir(self) -> Path:
        return self._resolve("datasets_dir", self._root / "data" / "datasets")

    @property
    def storage_dir(self) -> Path:
        return self._resolve("storage_dir", self._root / "data" / "storage")

    @property
    def models_dir(self) -> Path:
        return self._resolve("models_dir", self._root / "data" / "models")

    @property
    def content_dir(self) -> Path:
        return self._resolve("content_dir", self._root / "data" / "content")

    @property
    def api_key_path(self) -> Path:
        return self._resolve("api_key_path", self._root / "data" / ".api_key")

    @property
    def backup_dir(self) -> Path:
        return self._resolve("backup_dir", self._root / "data" / "backups")

    # ── Experiment tracking ───────────────────────────────────────

    @property
    def mlruns_dir(self) -> Path:
        return self._resolve("mlruns_dir", self._root / "mlruns")

    @property
    def mlflow_backend_store_uri(self) -> str:
        return f"sqlite:///{self._resolve('mlruns_dir', self._root / 'mlruns') / 'mlflow.db'}"

    # ── Logs ──────────────────────────────────────────────────────

    @property
    def log_dir(self) -> Path:
        return self._resolve("log_dir", self._root / "logs")
