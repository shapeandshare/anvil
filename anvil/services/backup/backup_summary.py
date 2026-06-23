# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Projection of a backup operation for list/UI display."""

from datetime import datetime

from pydantic import BaseModel


class BackupSummary(BaseModel):
    """Lightweight representation of a single backup for display.

    Parameters
    ----------
    backup_id : str
        Unique identifier.
    operation_type : str
        ``backup`` or ``pre_restore_safety``.
    status : str
        Current :class:`BackupStatus` value.
    created_at : datetime
        When the operation was created.
    archive_size_bytes : int
        Size of the compressed archive on disk.
    deployment_version : str or None
        anvil version at creation, if recorded.
    schema_revision : str or None
        Alembic head at creation, if recorded.
    age_seconds : int
        Seconds since ``created_at`` (computed at query time).
    is_safety_snapshot : bool
        ``True`` if ``operation_type == pre_restore_safety``.
    deletable : bool
        ``False`` for safety snapshots (blocked by FR-020).
    """

    backup_id: str
    operation_type: str
    status: str
    created_at: datetime
    archive_size_bytes: int = 0
    deployment_version: str | None = None
    schema_revision: str | None = None
    age_seconds: int = 0
    is_safety_snapshot: bool = False
    deletable: bool = True
