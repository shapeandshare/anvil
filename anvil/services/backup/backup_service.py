# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Process-lifetime BackupService — orchestrates backup/restore operations."""

import asyncio
import logging
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path

from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory

from ... import __version__ as anvil_version
from ...config import get_config
from ...db.models.backup_operation import BackupOperation
from ...db.repositories.backup_operations import BackupOperationRepository
from .archive_reader import ArchiveReader
from .archive_writer import ArchiveWriter
from .backup_lock import BackupLock
from .backup_status import BackupStatus
from .backup_storage_status import BackupStorageStatus
from .backup_summary import BackupSummary
from .create_backup_result import CreateBackupResult
from .progress_event import ProgressEvent
from .restore_engine import RestoreEngine
from .restore_journal import RestoreJournal
from .restore_preview import RestorePreview
from .retention_policy import RetentionPolicy
from .schema_compat_checker import check_schema_compatibility
from .snapshot_planner import SnapshotPlanner
from .verify_result import VerifyResult


def _get_alembic_head() -> str:
    """Return the current Alembic HEAD revision hash, or ``""``.

    Reads the Alembic migration files to determine the schema revision
    that the codebase expects.  This is a pure-filesystem operation —
    no database connection is needed.
    """
    try:
        package_root = Path(__file__).resolve().parent.parent.parent
        resources = package_root / "_resources"
        ini = str(resources / "alembic.ini")
        mig_dir = str(resources / "migrations")
        cfg = AlembicConfig(ini)
        cfg.set_main_option("script_location", mig_dir)
        script = ScriptDirectory.from_config(cfg)
        head = script.get_current_head()
        return head or ""
    except Exception:  # pylint: disable=broad-exception-caught
        return ""


class BackupService:
    """Orchestrates backup creation, restore, verification, and cleanup.

    This is a **process-lifetime** instance stored on
    ``app.state.backup_service``. It holds the single-operation
    ``BackupLock`` and manages progress queues for SSE streaming.
    Session-bound dependencies (repositories, audit) are passed at
    the method-call level by the route handler / CLI command.

    Parameters
    ----------
    backup_dir : str or None
        Path to the backup archive directory. Defaults to the config
        value ``backup_dir``.
    quota_bytes : int or None
        Hard storage quota. Defaults to the config value
        ``backup_quota_bytes``.
    warn_fraction : float or None
        Warning threshold fraction of quota. Defaults to config value
        ``backup_quota_warn_fraction``.
    retention_max_count : int or None
        Maximum non-safety backups before rotation. Defaults to config.
    retention_max_age_days : int or None
        Maximum age of non-safety backups before rotation. Defaults to
        config.
    """

    def __init__(
        self,
        backup_dir: str | None = None,
        quota_bytes: int | None = None,
        warn_fraction: float | None = None,
        _retention_max_count: int | None = None,
        _retention_max_age_days: int | None = None,
    ) -> None:
        cfg = get_config()
        self._loop = asyncio.get_running_loop()
        self._backup_dir = Path(backup_dir or cfg["backup_dir"])
        self._quota_bytes = quota_bytes or cfg["backup_quota_bytes"]
        self._warn_fraction = warn_fraction or cfg["backup_quota_warn_fraction"]
        self._retention_max_count = cfg["backup_retention_max_count"]
        self._retention_max_age_days = cfg["backup_retention_max_age_days"]
        self._lock = BackupLock()
        self._queues: dict[str, asyncio.Queue[ProgressEvent]] = {}

        # Sweep left-over .tmp/ and .restore-tmp/ dirs (FR-013).
        # The cwd-level .restore-tmp is the current location (feature-027
        # fix: was inside data/backups/ which caused self-referential move
        # failure during restore swaps).  The backup-dir-level location is
        # kept for backward compatibility with old temp dirs.
        tmp_dir = self._backup_dir / ".tmp"
        old_restore_tmp_dir = self._backup_dir / ".restore-tmp"
        restore_tmp_root = Path.cwd() / ".restore-tmp"
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)
        if old_restore_tmp_dir.exists():
            shutil.rmtree(old_restore_tmp_dir, ignore_errors=True)
        if restore_tmp_root.exists():
            shutil.rmtree(restore_tmp_root, ignore_errors=True)

    @property
    def lock(self) -> BackupLock:
        """Return the single-operation concurrency lock."""
        return self._lock

    # ── Implemented methods (Phase 3 — US1) ────────────────────────────

    async def create_backup(
        self,
        repo: BackupOperationRepository,
    ) -> CreateBackupResult:
        """Create a full deployment backup.

        Parameters
        ----------
        repo : BackupOperationRepository
            Session-bound repository for persisting the operation.

        Returns
        -------
        CreateBackupResult
            The backup identifier and any rotated backup ids.
        """
        backup_id = (
            datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + os.urandom(3).hex()
        )

        if not await self._lock.try_acquire("backup", backup_id):
            raise RuntimeError("A backup or restore operation is already in progress")

        try:
            planner = SnapshotPlanner()
            plan = planner.plan(self._backup_dir, self._quota_bytes)
            rotated_ids: list[str] = []

            if not plan.sufficient_space or not plan.within_quota:
                existing = await repo.get_all()
                policy = RetentionPolicy(
                    self._quota_bytes,
                    self._retention_max_count,
                    self._retention_max_age_days,
                )
                to_rotate = policy.select_for_rotation(
                    existing, plan.total_estimated_bytes
                )
                for rid in to_rotate:
                    await repo.delete(rid)
                    rotated_ids.append(rid)

                plan = planner.plan(self._backup_dir, self._quota_bytes)
                if not plan.sufficient_space or not plan.within_quota:
                    raise RuntimeError(
                        f"Insufficient space after rotation: need "
                        f"{plan.required_free_bytes} bytes, "
                        f"{plan.available_bytes} bytes available"
                    )

            op = BackupOperation(
                backup_id=backup_id,
                operation_type="backup",
                status=BackupStatus.CREATING.value,
            )
            await repo.add(op)

            queue: asyncio.Queue[ProgressEvent] = asyncio.Queue()
            self._queues[backup_id] = queue

            def _progress(pct: int, step: str) -> None:
                try:
                    fut = asyncio.run_coroutine_threadsafe(
                        queue.put(
                            ProgressEvent(
                                event="progress",
                                operation_type="backup",
                                backup_id=backup_id,
                                percent=float(pct),
                                current_step=step,
                            )
                        ),
                        self._loop,
                    )
                    fut.result(timeout=5)
                except (RuntimeError, TimeoutError, asyncio.CancelledError):
                    pass

            writer = ArchiveWriter(self._backup_dir)
            head_revision = _get_alembic_head()
            result = await writer.write(
                backup_id=backup_id,
                roots=plan.roots,
                operation_type="backup",
                progress_callback=_progress,
                schema_revision=head_revision,
            )

            await repo.update_fields(
                backup_id,
                status=BackupStatus.COMPLETED.value,
                archive_filename=result["archive_filename"],
                archive_size_bytes=result["archive_size_bytes"],
                total_uncompressed_bytes=result["total_uncompressed_bytes"],
                manifest_sha256=result["manifest_sha256"],
                deployment_version=result["deployment_version"],
                schema_revision=result["schema_revision"],
                completed_at=datetime.now(UTC),
            )

            await queue.put(
                ProgressEvent(
                    event="complete",
                    operation_type="backup",
                    backup_id=backup_id,
                    percent=100.0,
                    current_step="Complete",
                )
            )

            return CreateBackupResult(
                backup_id=backup_id, rotated_backup_ids=rotated_ids
            )

        except Exception:
            try:
                await repo.update_fields(backup_id, status=BackupStatus.FAILED.value)
            except Exception:  # pylint: disable=broad-exception-caught
                pass
            self._queues.pop(backup_id, None)
            raise

        finally:
            self._lock.release()

    async def list_backups(
        self, repo: BackupOperationRepository, include_safety: bool = True
    ) -> list[BackupSummary]:
        """Return all backup operations as summaries."""
        raw = await repo.get_all()
        now_dt = datetime.now(UTC)
        summaries: list[BackupSummary] = []
        for op in raw:
            if (
                not include_safety
                and getattr(op, "operation_type", "") == "pre_restore_safety"
            ):
                continue
            created = getattr(op, "created_at", None)
            age = 0
            if created is not None:
                if created.tzinfo is None:
                    created = created.replace(tzinfo=UTC)
                age = int((now_dt - created).total_seconds())
            summaries.append(
                BackupSummary(
                    backup_id=op.backup_id,
                    operation_type=op.operation_type,
                    status=op.status,
                    created_at=created or now_dt,
                    archive_size_bytes=op.archive_size_bytes or 0,
                    deployment_version=op.deployment_version,
                    schema_revision=op.schema_revision,
                    age_seconds=max(age, 0),
                    is_safety_snapshot=op.operation_type == "pre_restore_safety",
                    deletable=op.operation_type != "pre_restore_safety",
                )
            )
        return summaries

    async def get_backup(
        self, repo: BackupOperationRepository, backup_id: str
    ) -> BackupSummary | None:
        """Return a single backup summary."""
        op = await repo.get_by_backup_id(backup_id)
        if op is None:
            return None
        now_dt = datetime.now(UTC)
        created = getattr(op, "created_at", None)
        age = 0
        if created is not None:
            if created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            age = int((now_dt - created).total_seconds())
        return BackupSummary(
            backup_id=op.backup_id,
            operation_type=op.operation_type,
            status=op.status,
            created_at=created or now_dt,
            archive_size_bytes=op.archive_size_bytes or 0,
            deployment_version=op.deployment_version,
            schema_revision=op.schema_revision,
            age_seconds=max(age, 0),
            is_safety_snapshot=op.operation_type == "pre_restore_safety",
            deletable=op.operation_type != "pre_restore_safety",
        )

    # ── Stub methods (implemented in later phases) ───────────────────────

    async def storage_status(
        self, repo: BackupOperationRepository
    ) -> BackupStorageStatus:
        """Return aggregate storage statistics."""
        raw = await repo.get_all()
        total = sum(getattr(op, "archive_size_bytes", 0) or 0 for op in raw)
        count = len(raw)
        datetime.now(UTC)
        latest = raw[0].created_at if raw else None
        oldest = raw[-1].created_at if raw else None
        frac = total / self._quota_bytes if self._quota_bytes else 0
        return BackupStorageStatus(
            backup_count=count,
            total_bytes=total,
            quota_bytes=self._quota_bytes,
            quota_used_fraction=min(frac, 1.0),
            over_threshold=frac >= self._warn_fraction,
            latest_backup_at=latest,
            oldest_backup_at=oldest,
        )

    async def restore_preview(self, backup_id: str) -> RestorePreview:
        """Return restore preview for a given backup."""
        reader = ArchiveReader(self._backup_dir)
        manifest = await reader.load_manifest(backup_id)
        if manifest is None:
            raise ValueError(f"Backup not found: {backup_id}")

        compat, compat_detail = check_schema_compatibility(
            manifest_schema_revision=manifest.schema_revision,
            manifest_deployment_version=manifest.deployment_version,
            current_schema_revision=_get_alembic_head(),
            current_deployment_version=anvil_version,
        )

        planner = SnapshotPlanner()
        plan = planner.plan(self._backup_dir, self._quota_bytes)
        required = plan.total_estimated_bytes + plan.required_free_bytes

        return RestorePreview(
            backup_id=backup_id,
            created_at=manifest.created_at,
            archive_size_bytes=(
                sum(e.size for e in manifest.entries) if manifest.entries else 0
            ),
            total_uncompressed_bytes=manifest.total_uncompressed_bytes,
            entry_count=len(manifest.entries) if manifest.entries else 0,
            deployment_version=manifest.deployment_version,
            schema_revision=manifest.schema_revision,
            compatibility=compat.value,
            compatibility_detail=compat_detail,
            required_free_bytes=required,
            sufficient_space=True,
        )

    async def restore(
        self, backup_id: str, confirm: str, repo: BackupOperationRepository
    ) -> dict[str, str]:
        """Restore from a backup.

        Parameters
        ----------
        backup_id : str
            Which backup to restore.
        confirm : str
            Must equal ``"RESTORE"`` (FR-021).
        repo : BackupOperationRepository
            Session-bound repo for persisting the restore operation.

        Returns
        -------
        dict
            Keys: ``restore_operation_id``, ``safety_snapshot_id``.
        """
        if confirm != "RESTORE":
            raise ValueError("Confirmation token must be 'RESTORE'")

        head_revision = _get_alembic_head()

        # Check schema compatibility.
        reader = ArchiveReader(self._backup_dir)
        manifest = await reader.load_manifest(backup_id)
        if manifest is None:
            raise ValueError(f"Backup not found: {backup_id}")
        compat, compat_detail = check_schema_compatibility(
            manifest_schema_revision=manifest.schema_revision,
            manifest_deployment_version=manifest.deployment_version,
            current_schema_revision=head_revision,
            current_deployment_version=anvil_version,
        )
        if compat.value == "blocked":
            raise PermissionError(compat_detail)

        if not await self._lock.try_acquire("restore", backup_id):
            raise RuntimeError("A backup or restore operation is already in progress")

        try:
            # Auto-create pre-restore safety snapshot (inline, without
            # acquiring the lock — we already hold it).
            planner = SnapshotPlanner()
            plan = planner.plan(self._backup_dir, self._quota_bytes)
            safety_id = (
                datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + os.urandom(3).hex()
            )
            safety_op = BackupOperation(
                backup_id=safety_id,
                operation_type="pre_restore_safety",
                status=BackupStatus.CREATING.value,
            )
            await repo.add(safety_op)

            writer = ArchiveWriter(self._backup_dir)
            archive_result = await writer.write(
                backup_id=safety_id,
                roots=plan.roots,
                operation_type="pre_restore_safety",
                schema_revision=head_revision,
            )
            await repo.update_fields(
                safety_id,
                status=BackupStatus.COMPLETED.value,
                archive_filename=archive_result["archive_filename"],
                archive_size_bytes=archive_result["archive_size_bytes"],
                total_uncompressed_bytes=archive_result["total_uncompressed_bytes"],
                manifest_sha256=archive_result["manifest_sha256"],
                deployment_version=archive_result["deployment_version"],
                schema_revision=archive_result["schema_revision"],
            )
            safety_snapshot_id = safety_id

            restore_op = BackupOperation(
                backup_id=(
                    f"restore-{backup_id}-"
                    f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
                ),
                operation_type="restore",
                status=BackupStatus.CREATING.value,
                restored_from_backup_id=backup_id,
                safety_snapshot_id=safety_snapshot_id,
            )
            await repo.add(restore_op)

            journal_path = self._backup_dir / ".restore-journal.json"
            journal = RestoreJournal(journal_path)
            engine = RestoreEngine(self._backup_dir, journal)

            queue: asyncio.Queue[ProgressEvent] = asyncio.Queue()
            self._queues[safety_snapshot_id] = queue

            def _progress(pct: int, step: str) -> None:
                try:
                    fut = asyncio.run_coroutine_threadsafe(
                        queue.put(
                            ProgressEvent(
                                event="progress",
                                operation_type="restore",
                                backup_id=backup_id,
                                percent=float(pct),
                                current_step=step,
                                safety_snapshot_id=safety_snapshot_id,
                            )
                        ),
                        self._loop,
                    )
                    fut.result(timeout=5)
                except (RuntimeError, TimeoutError, asyncio.CancelledError):
                    pass

            result = await engine.execute(
                backup_id=backup_id,
                safety_snapshot_id=safety_snapshot_id,
                progress_callback=_progress,
            )

            if result.success:
                await repo.update_fields(
                    restore_op.backup_id,
                    status=BackupStatus.COMPLETED.value,
                    completed_at=datetime.now(UTC),
                )
                await queue.put(
                    ProgressEvent(
                        event="complete",
                        operation_type="restore",
                        backup_id=backup_id,
                        percent=100.0,
                        current_step="Complete",
                        safety_snapshot_id=safety_snapshot_id,
                    )
                )
            else:
                await repo.update_fields(
                    restore_op.backup_id,
                    status=BackupStatus.FAILED.value,
                    error_message=result.message,
                    completed_at=datetime.now(UTC),
                )
                await queue.put(
                    ProgressEvent(
                        event="error",
                        operation_type="restore",
                        backup_id=backup_id,
                        percent=0.0,
                        message=result.message,
                        safety_snapshot_id=safety_snapshot_id,
                    )
                )

            return {
                "restore_operation_id": restore_op.backup_id,
                "safety_snapshot_id": safety_snapshot_id,
                "status": (
                    BackupStatus.COMPLETED.value
                    if result.success
                    else BackupStatus.FAILED.value
                ),
            }

        finally:
            self._lock.release()

    async def recover_interrupted_restore(self) -> None:
        """Detect and recover from a crashed restore on startup."""
        journal_path = self._backup_dir / ".restore-journal.json"
        journal = RestoreJournal(journal_path)
        if journal.exists():
            result = journal.recover()
            logger = logging.getLogger(__name__)
            logger.warning(
                "Restore journal found during startup — recovering: %s",
                result.get("message"),
            )

    async def verify(
        self, backup_id: str, repo: BackupOperationRepository
    ) -> VerifyResult:
        """Verify integrity of a backup archive."""
        reader = ArchiveReader(self._backup_dir)
        result = await reader.verify(backup_id)
        if not result.valid:
            try:
                await repo.update_fields(backup_id, status=BackupStatus.CORRUPTED.value)
            except Exception:  # pylint: disable=broad-exception-caught
                pass
        return result

    async def delete_backup(
        self,
        backup_id: str,
        repo: BackupOperationRepository,
        confirm_last: bool = False,
    ) -> None:
        """Delete a backup archive and its DB record."""
        op = await repo.get_by_backup_id(backup_id)
        if op is None:
            raise ValueError(f"Backup not found: {backup_id}")
        if getattr(op, "operation_type", "") == "pre_restore_safety":
            raise PermissionError(
                "Safety snapshots cannot be deleted via this path. "
                "Use the safety-snapshot cleanup action (FR-020)."
            )
        # Check if this is the last restorable backup.
        all_ops = await repo.get_all_restorable()
        restorable = [
            b
            for b in all_ops
            if b.backup_id != backup_id
            and getattr(b, "operation_type", "") != "pre_restore_safety"
            and getattr(b, "status", "") == BackupStatus.COMPLETED.value
        ]
        if not restorable and not confirm_last:
            raise PermissionError(
                "This is the only remaining backup. Deleting it leaves "
                "no recovery option. Use --confirm-last to override."
            )
        archive_path = self._backup_dir / f"backup-{backup_id}.tar.gz"
        if archive_path.exists():
            archive_path.unlink()
        await repo.delete(backup_id)

    async def cleanup_safety(self, repo: BackupOperationRepository) -> int:
        """Remove pre-restore safety snapshots and return count."""
        all_ops = await repo.get_all()
        safety = [
            b
            for b in all_ops
            if getattr(b, "operation_type", "") == "pre_restore_safety"
        ]
        count = 0
        for op in safety:
            archive_path = self._backup_dir / f"backup-{op.backup_id}.tar.gz"
            if archive_path.exists():
                archive_path.unlink()
            await repo.delete(op.backup_id)
            count += 1
        return count

    def stream_for(self, operation_id: str) -> asyncio.Queue[ProgressEvent] | None:
        """Return the progress queue for an in-flight operation."""
        return self._queues.get(operation_id)
