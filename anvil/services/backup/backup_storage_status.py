# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Aggregate backup-storage statistics for the Operations status card."""

from datetime import datetime

from pydantic import BaseModel


class BackupStorageStatus(BaseModel):
    """Summary of backup storage usage, driving the quota gauge.

    Parameters
    ----------
    backup_count : int
        Number of backup archives on disk.
    total_bytes : int
        Sum of archive sizes.
    quota_bytes : int
        Configured storage cap.
    quota_used_fraction : float
        ``total_bytes / quota_bytes``, clamped to ``[0, 1]``.
    over_threshold : bool
        ``quota_used_fraction >= warn_fraction`` from config.
    latest_backup_at : datetime or None
        Timestamp of the most recent backup.
    oldest_backup_at : datetime or None
        Timestamp of the oldest backup.
    """

    backup_count: int = 0
    total_bytes: int = 0
    quota_bytes: int = 10 * 1024**3
    quota_used_fraction: float = 0.0
    over_threshold: bool = False
    latest_backup_at: datetime | None = None
    oldest_backup_at: datetime | None = None
