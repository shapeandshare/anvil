# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Reads and verifies backup archives — integrity checks and safe
extraction.
"""

import asyncio
import hashlib
import json
import tarfile
from pathlib import Path
from typing import Any

from .backup_manifest import BackupManifest
from .verify_result import VerifyResult


class ArchiveReader:
    """Opens a ``.tar.gz`` backup archive and provides verification &
    extraction.

    All blocking I/O (``tarfile``, ``hashlib``) runs inside
    ``asyncio.to_thread``.
    """

    def __init__(self, backup_dir: str | Path) -> None:
        self._backup_dir = Path(backup_dir)

    # ── Public API ───────────────────────────────────────────────────────

    async def verify(self, backup_id: str) -> VerifyResult:
        """Recompute checksums for every file in the archive and compare
        against the manifest.

        Parameters
        ----------
        backup_id : str
            The backup identifier (also the archive filename prefix).

        Returns
        -------
        VerifyResult
            ``valid`` = True when every file's SHA-256 matches.
        """
        return await asyncio.to_thread(self._verify_sync, backup_id)

    async def extract_to(self, backup_id: str, dest: Path) -> BackupManifest:
        """Extract the archive to *dest* and return its manifest.

        Performs path-traversal rejection and ``manifest_version``
        gating during extraction.
        """
        return await asyncio.to_thread(self._extract_sync, backup_id, dest)

    async def load_manifest(self, backup_id: str) -> BackupManifest | None:
        """Read the manifest without extracting files."""
        return await asyncio.to_thread(self._load_manifest_sync, backup_id)

    # ── Synchronous implementations ──────────────────────────────────────

    def _archive_path(self, backup_id: str) -> Path:
        return self._backup_dir / f"backup-{backup_id}.tar.gz"

    def _verify_sync(self, backup_id: str) -> VerifyResult:
        path = self._archive_path(backup_id)
        if not path.exists():
            return VerifyResult(backup_id=backup_id, valid=False, checked_count=0)

        entries_map = self._read_manifest_and_entries(path)[1]
        mismatched: list[str] = []
        checked = 0

        with tarfile.open(path, "r:gz") as tar:
            for member in tar.getmembers():
                if member.name == "manifest.json":
                    continue
                f = tar.extractfile(member)
                if f is None:
                    mismatched.append(member.name)
                    continue
                h = hashlib.sha256()
                while chunk := f.read(65536):
                    h.update(chunk)
                digest = h.hexdigest()
                expected = entries_map.get(member.name, {}).get("sha256", "")
                checked += 1
                if digest != expected:
                    mismatched.append(member.name)

        return VerifyResult(
            backup_id=backup_id,
            valid=len(mismatched) == 0,
            checked_count=checked,
            mismatched=mismatched,
        )

    def _extract_sync(self, backup_id: str, dest: Path) -> BackupManifest:
        path = self._archive_path(backup_id)
        dest.mkdir(parents=True, exist_ok=True)
        manifest, _ = self._read_manifest_and_entries(path)

        if manifest.manifest_version > 1:
            raise ValueError(
                f"Unsupported manifest version {manifest.manifest_version}. "
                f"This reader supports v1."
            )

        with tarfile.open(path, "r:gz") as tar:
            for member in tar.getmembers():
                if member.name == "manifest.json":
                    continue
                # Path-traversal check.
                resolved = (dest / member.name).resolve()
                if not str(resolved).startswith(str(dest.resolve())):
                    raise ValueError(f"Path traversal in archive: {member.name}")
                tar.extract(member, path=dest)

        return manifest

    def _load_manifest_sync(self, backup_id: str) -> BackupManifest | None:
        path = self._archive_path(backup_id)
        if not path.exists():
            return None
        manifest, _ = self._read_manifest_and_entries(path)
        return manifest

    # ── Shared helpers ───────────────────────────────────────────────────

    @staticmethod
    def _read_manifest_and_entries(
        path: Path,
    ) -> tuple[BackupManifest, dict[str, Any]]:
        """Open archive, extract manifest, return (manifest, entries_map)."""
        with tarfile.open(path, "r:gz") as tar:
            manifest_member = tar.getmember("manifest.json")
            f = tar.extractfile(manifest_member)
            if f is None:
                raise ValueError("manifest.json is empty or missing")
            data = json.loads(f.read())
            manifest = BackupManifest(**data)
            entries_map = {e["path"]: e for e in data.get("entries", [])}
        return manifest, entries_map
