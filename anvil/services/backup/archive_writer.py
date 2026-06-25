# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Produces consistent, immutable backup archives with integrity
manifests.
"""

import asyncio
import hashlib
import io
import os
import sqlite3
import tarfile
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ... import __version__ as anvil_version
from .backup_manifest import BackupManifest
from .manifest_entry import ManifestEntry


class ArchiveWriter:
    """Creates a ``.tar.gz`` backup archive from a set of managed roots.

    Each archive contains a ``manifest.json`` as its first member,
    followed by every managed file.  The write is atomic: data is
    assembled in a ``.tmp/`` staging directory, then moved into place
    via ``os.replace``.

    All blocking I/O (``tarfile``, ``hashlib``, ``sqlite3``) runs
    inside ``asyncio.to_thread`` so the event loop is not blocked.
    """

    def __init__(self, backup_dir: str | Path) -> None:
        self._backup_dir = Path(backup_dir)
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        self._tmp_dir = self._backup_dir / ".tmp"
        self._tmp_dir.mkdir(parents=True, exist_ok=True)

    # ── Public API ───────────────────────────────────────────────────────

    async def write(
        self,
        backup_id: str,
        roots: list[Path],
        operation_type: str = "backup",
        progress_callback: Callable[[int, str], None] | None = None,
    ) -> dict[str, Any]:
        """Create a backup archive and return manifest metadata.

        Parameters
        ----------
        backup_id : str
            Unique identifier (becomes part of the filename).
        roots : list[Path]
            Filesystem roots to include in the archive.
        operation_type : str
            ``"backup"`` or ``"pre_restore_safety"``.
        progress_callback : callable or None
            Called with ``(percent, step_label)`` during archiving.

        Returns
        -------
        dict
            Keys ``archive_filename``, ``archive_size_bytes``,
            ``total_uncompressed_bytes``, ``manifest_sha256``,
            ``deployment_version``, and ``schema_revision`` for
            persisting to the ``BackupOperation`` DB row.
        """
        return await asyncio.to_thread(
            self._write_sync,
            backup_id,
            roots,
            operation_type,
            progress_callback,
        )

    # ── Synchronous implementation (runs in a thread) ────────────────────

    def _write_sync(
        self,
        backup_id: str,
        roots: list[Path],
        operation_type: str,
        progress_callback: Callable[[int, str], None] | None,
    ) -> dict[str, Any]:
        filename = f"backup-{backup_id}.tar.gz"
        tmp_path = self._tmp_dir / f"{filename}.part"
        final_path = self._backup_dir / filename

        entries: list[ManifestEntry] = []
        total_bytes = 0

        # Phase 1 — WAL-consistent DB snapshot.
        self._notify(progress_callback, 5, "Snapshotting database")
        db_snapshot = self._snapshot_db(Path("data/anvil-state.db"), self._tmp_dir)
        additional_roots = []
        if db_snapshot is not None:
            additional_roots = [db_snapshot]

        # Phase 2 — Collect all files.
        self._notify(progress_callback, 10, "Collecting files")
        all_roots = list(roots) + additional_roots
        file_list: list[tuple[str, Path]] = []
        cwd = Path.cwd()
        for root in all_roots:
            if root.is_file():
                # Skip files inside the backup directory (snapshot temps).
                if str(root).startswith(str(self._backup_dir)):
                    continue
                rel = self._archive_path(root, cwd)
                file_list.append((rel, root))
            elif root.is_dir():
                for fpath in sorted(root.rglob("*")):
                    if not fpath.is_file():
                        continue
                    # Skip files inside the backup directory (snapshot
                    # temps, .tmp, .restore-tmp).
                    if str(fpath).startswith(str(self._backup_dir)):
                        continue
                    rel = self._archive_path(fpath, cwd)
                    file_list.append((rel, fpath))

        # Phase 3 — Build archive.
        self._notify(progress_callback, 20, "Creating archive")
        with tarfile.open(tmp_path, "w:gz") as tar:

            # Phase 4 — Write manifest first.
            self._notify(progress_callback, 25, "Building manifest")
            for arcname, fspath in file_list:
                sha256 = self._hash_file(fspath)
                size = fspath.stat().st_size
                entries.append(ManifestEntry(path=arcname, sha256=sha256, size=size))
                total_bytes += size

            manifest = BackupManifest(
                manifest_version=1,
                backup_id=backup_id,
                created_at=datetime.now(UTC),
                operation_type=operation_type,
                deployment_version=anvil_version,
                schema_revision="",  # caller can set via return value
                total_uncompressed_bytes=total_bytes,
                entries=entries,
            )
            manifest_bytes = manifest.model_dump_json(indent=2).encode("utf-8")
            manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
            info = tarfile.TarInfo(name="manifest.json")
            info.size = len(manifest_bytes)
            tar.addfile(info, io.BytesIO(manifest_bytes))

            # Phase 5 — Add all files.
            self._notify(progress_callback, 40, "Archiving files")
            for i, (arcname, fspath) in enumerate(file_list):
                tar.add(fspath, arcname=arcname, recursive=False)
                pct = 40 + int(60 * (i + 1) / len(file_list))
                self._notify(progress_callback, pct, f"Archiving {arcname}")

        # Phase 6 — Atomic replace.
        self._notify(progress_callback, 98, "Finalizing")
        os.replace(tmp_path, final_path)
        archive_size = final_path.stat().st_size

        # Clean up temp DB snapshot.
        if db_snapshot is not None:
            db_snapshot.unlink(missing_ok=True)

        self._notify(progress_callback, 100, "Complete")

        return {
            "archive_filename": filename,
            "archive_size_bytes": archive_size,
            "total_uncompressed_bytes": total_bytes,
            "manifest_sha256": manifest_sha256,
            "deployment_version": anvil_version,
            "schema_revision": "",
        }

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _archive_path(path: Path, cwd: Path) -> str:
        """Compute the archive member path for *path*.

        Prefers a path relative to *cwd* (production case); falls back
        to the file name (test/unusual cases).
        """
        try:
            return str(path.relative_to(cwd))
        except ValueError:
            return path.name

    @staticmethod
    def _snapshot_db(db_path: Path, tmp_dir: Path | None = None) -> Path | None:
        """Produce a consistent single-file copy of a WAL-mode SQLite DB.

        Uses ``sqlite3.Connection.backup()`` to merge the WAL pages
        into the destination — safe even while the source is being
        written.  The snapshot is placed in *tmp_dir* (or the DB's
        parent) to avoid polluting managed roots.
        """
        if not db_path.exists():
            return None
        target_dir = tmp_dir or db_path.parent
        target_dir.mkdir(parents=True, exist_ok=True)
        fd, tmp_path_str = tempfile.mkstemp(suffix=".db", dir=str(target_dir))
        os.close(fd)
        tmp = Path(tmp_path_str)
        src = sqlite3.connect(str(db_path))
        dst = sqlite3.connect(str(tmp))
        try:
            src.backup(dst, pages=0)  # 0 = all pages
        finally:
            src.close()
            dst.close()
        return tmp

    @staticmethod
    def _hash_file(path: Path) -> str:
        """Return hex SHA-256 of *path*."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _notify(cb: Callable[[int, str], None] | None, percent: int, step: str) -> None:
        """Call the progress callback if one was provided."""
        if cb is not None:
            try:
                cb(percent, step)
            except Exception:
                pass
