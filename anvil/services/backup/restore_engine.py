# one-class:allow — RestoreResult is the return type of RestoreEngine
# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Atomic restore engine — extract, verify, journal, swap, rollback."""

import shutil
from collections.abc import Callable
from pathlib import Path

from .archive_reader import ArchiveReader
from .restore_journal import RestoreJournal


#: Name of the staging directory at the project root (outside managed
#: roots such as ``data/`` so that swapping a root does not orphan the
#: staging directory).
_RESTORE_TMP_NAME = ".restore-tmp"


class RestoreResult:
    """Result of a restore operation.

    Parameters
    ----------
    success : bool
        Whether the restore completed cleanly.
    safety_snapshot_id : str or None
        The pre-restore safety snapshot id for undo.
    message : str
        Human-readable summary of the outcome.
    """

    def __init__(
        self,
        success: bool = False,
        safety_snapshot_id: str | None = None,
        message: str = "",
    ) -> None:
        self.success = success
        self.safety_snapshot_id = safety_snapshot_id
        self.message = message


class RestoreEngine:
    """Applies a backup archive to the live deployment.

    Uses an **atomic swap pattern**: files are first extracted to a
    temporary directory and verified against the manifest.  Then a
    restore journal is written (FR-030), the live roots are moved
    aside to ``.bak`` copies, and the restored files are moved into
    place.  On any failure the ``.bak`` copies are restored.  On
    complete success the journal and ``.bak`` copies are removed.

    Parameters
    ----------
    backup_dir : Path
        The directory containing backup archives.
    journal : RestoreJournal
        Journal for crash-safe recovery.
    """

    def __init__(self, backup_dir: Path, journal: RestoreJournal) -> None:
        self._backup_dir = backup_dir
        self._journal = journal

    async def execute(
        self,
        backup_id: str,
        safety_snapshot_id: str,
        progress_callback: Callable[[int, str], None] | None = None,
    ) -> RestoreResult:
        """Run the full restore pipeline.

        Parameters
        ----------
        backup_id : str
            The backup to restore from.
        safety_snapshot_id : str
            The pre-restore safety snapshot id for the journal.
        progress_callback : callable or None
            Called with ``(percent, step)`` during restore.

        Returns
        -------
        RestoreResult
        """
        reader = ArchiveReader(self._backup_dir)

        self._notify(progress_callback, 5, "Reading manifest")
        manifest = await reader.load_manifest(backup_id)
        if manifest is None:
            return RestoreResult(
                success=False,
                safety_snapshot_id=safety_snapshot_id,
                message=f"Backup not found: {backup_id}",
            )

        self._notify(progress_callback, 15, "Extracting to temp directory")
        restore_tmp = Path.cwd() / _RESTORE_TMP_NAME / backup_id
        if restore_tmp.exists():
            shutil.rmtree(restore_tmp, ignore_errors=True)
        restore_tmp.mkdir(parents=True, exist_ok=True)

        try:
            await reader.extract_to(backup_id, restore_tmp)
            self._notify(progress_callback, 60, "Verifying extracted files")

            result = await reader.verify(backup_id)
            if not result.valid:
                return RestoreResult(
                    success=False,
                    safety_snapshot_id=safety_snapshot_id,
                    message=f"Integrity check failed for backup {backup_id}",
                )

            self._notify(progress_callback, 75, "Swapping files (atomic)")

            # Derive managed roots from the ACTUAL extracted content —
            # do NOT hardcode, because the archive structure depends on
            # which roots were present at backup time (FR-030).
            managed_dirs: list[str] = [
                p.name for p in sorted(restore_tmp.iterdir()) if p.is_dir()
            ]

            journal_roots: list[str] = []
            for md in managed_dirs:
                restored = restore_tmp / md
                live = Path.cwd() / md
                bak = Path(str(live) + ".bak")
                if restored.exists():
                    journal_roots.append(str(live))

            if not journal_roots:
                return RestoreResult(
                    success=False,
                    safety_snapshot_id=safety_snapshot_id,
                    message=(
                        "No root directories found in extracted backup — "
                        "archive appears empty."
                    ),
                )

            # Write journal before swapping.
            self._journal.write(
                restore_operation_id=backup_id,
                source_backup_id=backup_id,
                safety_snapshot_id=safety_snapshot_id,
                roots=journal_roots,
            )

            # Swap each root.
            for md in managed_dirs:
                restored = restore_tmp / md
                live = Path.cwd() / md
                bak = Path(str(live) + ".bak")
                if not restored.exists():
                    continue
                # Move live aside to .bak.
                if live.exists():
                    if bak.exists():
                        shutil.rmtree(bak, ignore_errors=True)
                    shutil.move(str(live), str(bak))
                # Move restored into place.
                shutil.move(str(restored), str(live))

            self._notify(progress_callback, 90, "Cleaning up")

            # Remove .bak copies on full success.
            for md in managed_dirs:
                restored = restore_tmp / md
                live = Path.cwd() / md
                bak = Path(str(live) + ".bak")
                if bak.exists():
                    if bak.is_dir():
                        shutil.rmtree(bak, ignore_errors=True)
                    else:
                        bak.unlink(missing_ok=True)

            # Clear journal.
            self._journal.clear()

            self._notify(progress_callback, 100, "Restore complete")

            return RestoreResult(
                success=True,
                safety_snapshot_id=safety_snapshot_id,
                message=f"Restore from {backup_id} completed successfully.",
            )

        except Exception as exc:
            # Rollback on any failure.
            managed_dirs = (
                [p.name for p in sorted(restore_tmp.iterdir()) if p.is_dir()]
                if restore_tmp.exists()
                else []
            )
            for md in managed_dirs:
                live = Path.cwd() / md
                bak = Path(str(live) + ".bak")
                if bak.exists():
                    if live.exists():
                        if live.is_dir():
                            shutil.rmtree(live, ignore_errors=True)
                        else:
                            live.unlink(missing_ok=True)
                    shutil.move(str(bak), str(live))

            return RestoreResult(
                success=False,
                safety_snapshot_id=safety_snapshot_id,
                message=f"Restore failed: {exc}",
            )

        finally:
            # Clean up temp extraction.
            if restore_tmp.exists():
                shutil.rmtree(restore_tmp, ignore_errors=True)

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _notify(cb: Callable[[int, str], None] | None, percent: int, step: str) -> None:
        if cb is not None:
            try:
                cb(percent, step)
            except Exception:
                pass
