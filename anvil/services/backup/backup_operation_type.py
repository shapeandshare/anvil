# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Types of backup/restore operations recorded in the history table."""

from enum import StrEnum


class BackupOperationType(StrEnum):
    """Distinguishes manual backups, restores, and auto safety snapshots."""

    BACKUP = "backup"
    RESTORE = "restore"
    PRE_RESTORE_SAFETY = "pre_restore_safety"
