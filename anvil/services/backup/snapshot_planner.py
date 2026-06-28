# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Plans which paths to include in a backup snapshot and pre-flights
space/quota.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from ...workspace.workspace_paths import WorkspacePaths


@dataclass  # noqa: dataclass
class SnapshotPlan:
    """Result of planning a snapshot — the set of roots to archive and
    whether pre-flight checks passed.

    Parameters
    ----------
    roots : list[Path]
        Filesystem roots to include in the archive.
    total_estimated_bytes : int
        Sum of sizes of all roots (uncompressed estimate).
    required_free_bytes : int
        Estimated space needed for the temp write + archive.
    available_bytes : int
        Free bytes on the backup volume.
    sufficient_space : bool
        Whether available >= required.
    within_quota : bool
        Whether total fits in the configured quota (projected).
    """

    roots: list[Path] = field(default_factory=list)
    total_estimated_bytes: int = 0
    required_free_bytes: int = 0
    available_bytes: int = 0
    sufficient_space: bool = True
    within_quota: bool = True


class SnapshotPlanner:
    """Determines which paths to back up and validates space/quota
    constraints.

    ``INCLUDED_ROOTS`` are the persistent filesystem roots that form
    the deployment state.  ``EXCLUDED_ROOTS`` are deliberately omitted
    (diagnostic-only logs, environment-specific config/secrets).

    When *workspace_root* is provided, paths are resolved via
    :class:`WorkspacePaths` instead of ``Path.cwd()`` — this ensures
    backups respect the per-instance workspace layout.
    """

    INCLUDED_ROOTS: ClassVar[list[str]] = [
        "data/anvil-state.db",
        "data/models",
        "data/datasets",
        "data/storage",
        "data/content",
        "mlruns",
    ]

    EXCLUDED_ROOTS: ClassVar[list[str]] = [
        "logs",
        ".env",
    ]

    #: Maps INCLUDED_ROOTS entries to WorkspacePaths property names.
    _ROOT_TO_WP_PROP: ClassVar[dict[str, str]] = {
        "data/anvil-state.db": "state_db_path",
        "data/models": "models_dir",
        "data/datasets": "datasets_dir",
        "data/storage": "storage_dir",
        "data/content": "content_dir",
        "mlruns": "mlruns_dir",
    }

    def __init__(self, workspace_root: Path | None = None) -> None:
        """Initialise the planner.

        Parameters
        ----------
        workspace_root : Path or None
            Optional workspace root.  When set, paths in ``plan()`` are
            resolved via :class:`WorkspacePaths` instead of the current
            working directory.
        """
        self._workspace_root = workspace_root

    @staticmethod
    def _dir_size(path: Path) -> int:
        """Recursively sum file sizes under *path*."""
        total = 0
        try:
            for entry in path.rglob("*"):
                if entry.is_file():
                    total += entry.stat().st_size
        except OSError:
            pass  # path may not exist yet — treat as 0
        return total

    def plan(
        self,
        backup_dir: Path,
        quota_bytes: int,
    ) -> SnapshotPlan:
        """Build a :class:`SnapshotPlan` for the current deployment.

        Parameters
        ----------
        backup_dir : Path
            The backup archive output directory (``data/backups/``),
            used to determine the target volume for space checks.
        quota_bytes : int
            Configured storage quota for backup archives.

        Returns
        -------
        SnapshotPlan
            The plan with pre-flight results.
        """
        cwd = Path.cwd()
        backup_dir.mkdir(parents=True, exist_ok=True)
        roots: list[Path] = []
        total = 0

        if self._workspace_root is not None:
            wp = WorkspacePaths(self._workspace_root)
            for rel in self.INCLUDED_ROOTS:
                prop = self._ROOT_TO_WP_PROP[rel]
                p: Path = getattr(wp, prop)
                if not p.exists():
                    continue
                roots.append(p)
                if p.is_file():
                    total += p.stat().st_size
                else:
                    total += self._dir_size(p)
        else:
            for rel in self.INCLUDED_ROOTS:
                p = cwd / rel
                if not p.exists():
                    continue
                roots.append(p)
                if p.is_file():
                    total += p.stat().st_size
                else:
                    total += self._dir_size(p)

        required = int(total * 1.1)  # 10% safety margin for the temp copy
        try:
            usage = shutil.disk_usage(backup_dir)
            available = usage.free
        except OSError:
            available = 0

        return SnapshotPlan(
            roots=roots,
            total_estimated_bytes=total,
            required_free_bytes=required,
            available_bytes=available,
            sufficient_space=available >= required,
            within_quota=total <= quota_bytes,
        )


# Late import for disk_usage (stdlib, no circular dep).
import shutil  # noqa: E402 — placed after class to keep dataclass import clean
