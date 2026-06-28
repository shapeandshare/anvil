# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Workspace lock management for isolated instances.

Provides :class:`WorkspaceLock` for acquiring and releasing
per-workspace lock files (``.anvil-lock``).  A lock file contains the
PID of the process that holds the lock, enabling stale-lock detection
and reclamation.

Lock file location
------------------
``{workspace_root}/.anvil-lock`` — a single text file containing the
holding process's PID as a decimal string.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_LOCK_FILENAME: str = ".anvil-lock"


class WorkspaceLock:
    """Per-workspace PID-based lock for preventing concurrent access.

    The lock file lives at ``{workspace_root}/.anvil-lock`` and
    contains the PID of the process that holds the lock as a plain
    decimal string.

    Parameters
    ----------
    workspace_root : Path
        Absolute path to the workspace root directory.
    """

    def __init__(self, workspace_root: Path) -> None:
        self._workspace_root = workspace_root.resolve()
        self._lock_path = self._workspace_root / _LOCK_FILENAME

    @property
    def lock_path(self) -> Path:
        """Path to the ``.anvil-lock`` file on disk."""
        return self._lock_path

    async def acquire(self) -> bool:
        """Acquire the workspace lock.

        Writes the current process PID to ``.anvil-lock``.  If the lock
        file already exists and the recorded PID belongs to a live
        process, the lock is **not** acquired and ``False`` is returned.

        If the recorded PID is dead (stale lock), the lock file is
        silently overwritten.

        Returns
        -------
        bool
            ``True`` if the lock was acquired, ``False`` if it is held
            by another live process.
        """
        if self._lock_path.exists():
            existing_pid = int(self._lock_path.read_text().strip())
            if _pid_alive(existing_pid):
                return False
            # Stale lock — clean it.
            self._lock_path.unlink(missing_ok=True)

        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_path.write_text(str(os.getpid()))
        logger.debug("Acquired workspace lock at %s", self._lock_path)
        return True

    async def release(self) -> None:
        """Release the workspace lock by removing the ``.anvil-lock`` file.

        Idempotent — succeeds even if the lock file does not exist.
        """
        self._lock_path.unlink(missing_ok=True)
        logger.debug("Released workspace lock at %s", self._lock_path)

    @classmethod
    async def reclaim(cls, workspace_root: Path) -> bool:
        """Check whether a workspace lock is stale and reclaim it.

        Reads the PID from ``.anvil-lock``.  If the recorded PID is
        dead, the lock file is removed and ``True`` is returned.  If
        the PID is still alive (or no lock file exists), ``False`` is
        returned.

        Parameters
        ----------
        workspace_root : Path
            Absolute path to the workspace root directory.

        Returns
        -------
        bool
            ``True`` if a stale lock was found and reclaimed.
        """
        lock_path = workspace_root.resolve() / _LOCK_FILENAME
        if not lock_path.exists():
            return False

        pid = int(lock_path.read_text().strip())
        if not _pid_alive(pid):
            lock_path.unlink(missing_ok=True)
            logger.info("Reclaimed stale workspace lock (PID %d) at %s", pid, lock_path)
            return True

        return False


def _pid_alive(pid: int) -> bool:
    """Check whether a process with the given PID is alive.

    Uses ``os.kill(pid, 0)`` — a no-op signal that only checks for
    process existence.

    Parameters
    ----------
    pid : int
        Process ID to check.

    Returns
    -------
    bool
        ``True`` if the process exists.
    """
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False
