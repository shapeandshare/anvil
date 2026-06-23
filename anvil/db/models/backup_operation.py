# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""BackupOperation ORM model for tracking backup/restore operations."""

from datetime import datetime

from sqlalchemy import Integer, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base
from ..timestamp_mixin import TimestampMixin


class BackupOperation(Base, TimestampMixin):
    """A persisted record of a backup or restore operation.

    Maps to the ``backup_operations`` table. This is the queryable
    index and history log; the archive file on disk is the source
    of truth for contents.

    Mapped columns
    --------------
    id : int
        Primary key, auto-increment.
    backup_id : str
        Public identifier (e.g. ``20260621T143000Z-a1b2c3``), unique
        and indexed.
    operation_type : str
        ``BackupOperationType`` value (``backup``, ``restore``, or
        ``pre_restore_safety``).
    status : str
        ``BackupStatus`` value (``creating``, ``completed``, ``failed``,
        ``corrupted``).
    archive_filename : str or None
        Filename in the backup dir; ``None`` until the archive is
        written.
    archive_size_bytes : int
        Compressed archive size.
    total_uncompressed_bytes : int
        Sum of source file sizes before compression.
    manifest_sha256 : str or None
        Top-level manifest checksum for integrity verification.
    deployment_version : str or None
        ``anvil.__version__`` at the time of creation.
    schema_revision : str or None
        Alembic head revision at the time of creation.
    started_at : datetime or None
        When the operation began.
    completed_at : datetime or None
        When the operation ended (success or failure).
    error_message : str or None
        Populated on failure.
    restored_from_backup_id : str or None
        For ``restore`` rows: which backup was restored.
    safety_snapshot_id : str or None
        For ``restore`` rows: the auto-created pre-restore snapshot id.
    """

    __tablename__ = "backup_operations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    backup_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    operation_type: Mapped[str] = mapped_column(String(20), default="backup")
    status: Mapped[str] = mapped_column(String(20), default="creating")
    archive_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    archive_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    total_uncompressed_bytes: Mapped[int] = mapped_column(Integer, default=0)
    manifest_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    deployment_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    schema_revision: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    restored_from_backup_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    safety_snapshot_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
