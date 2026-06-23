# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Crash-safe restore journal — marker file written before the file-swap
phase begins (FR-030).
"""

import json
from datetime import UTC, datetime
from pathlib import Path


class RestoreJournal:
    """A marker file written before the restore's file-swap phase and
    removed only after a clean, fully-verified completion.

    If the process crashes mid-restore, the presence of this journal
    at startup signals an interrupted restore (R13).  The journal
    records enough information to either roll back from the moved-aside
    ``.bak`` copies or surface a recovery prompt pointing to the
    pre-restore safety snapshot.

    Parameters
    ----------
    journal_path : Path
        Filesystem path for the journal file (recommended:
        ``data/backups/.restore-journal.json``).
    """

    def __init__(self, journal_path: Path) -> None:
        self._path = journal_path

    def write(
        self,
        restore_operation_id: str,
        source_backup_id: str,
        safety_snapshot_id: str,
        roots: list[str],
    ) -> None:
        """Write the journal before starting the swap phase.

        Parameters
        ----------
        restore_operation_id : str
            The in-flight restore operation id.
        source_backup_id : str
            The backup being restored.
        safety_snapshot_id : str
            The pre-restore safety snapshot id for recovery.
        roots : list[str]
            Managed roots being swapped.
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "restore_operation_id": restore_operation_id,
            "source_backup_id": source_backup_id,
            "safety_snapshot_id": safety_snapshot_id,
            "roots": roots,
            "phase": "swapping",
            "created_at": datetime.now(UTC).isoformat(),
        }
        self._path.write_text(json.dumps(data, indent=2))

    def clear(self) -> None:
        """Remove the journal (called after a clean restore)."""
        if self._path.exists():
            self._path.unlink()

    def exists(self) -> bool:
        """Return ``True`` if a journal is present."""
        return self._path.exists()

    def read(self) -> dict | None:
        """Read and return the journal contents, or ``None`` if absent."""
        if not self._path.exists():
            return None
        try:
            return json.loads(self._path.read_text())
        except (json.JSONDecodeError, OSError):
            return None

    def recover(self) -> dict:
        """Attempt recovery from an interrupted restore.

        Returns a dict with keys:
        - ``recovered`` (bool): whether rollback succeeded.
        - ``safety_snapshot_id`` (str or None): fallback if rollback
          is impossible.
        - ``message`` (str): human-readable recovery status.
        """
        data = self.read()
        if data is None:
            return {
                "recovered": False,
                "safety_snapshot_id": None,
                "message": "No restore journal found.",
            }

        safety_id = data.get("safety_snapshot_id")
        roots = data.get("roots", [])

        # Try to roll back each root from its .bak copy.
        all_rolled_back = True
        for rel in roots:
            bak_path = Path(rel + ".bak")
            live_path = Path(rel)
            if bak_path.exists():
                try:
                    if live_path.exists():
                        import shutil

                        shutil.rmtree(live_path, ignore_errors=True)
                        live_path.unlink(missing_ok=True)
                    bak_path.rename(live_path)
                except Exception:
                    all_rolled_back = False

        if all_rolled_back:
            self.clear()
            return {
                "recovered": True,
                "safety_snapshot_id": safety_id,
                "message": "Restore rolled back successfully from .bak copies.",
            }

        return {
            "recovered": False,
            "safety_snapshot_id": safety_id,
            "message": (
                f"Interrupted restore from backup {data.get('source_backup_id')} "
                f"could not be fully rolled back. "
                f"Pre-restore safety snapshot: {safety_id}"
            ),
        }
