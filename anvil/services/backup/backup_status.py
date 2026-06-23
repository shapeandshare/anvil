# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Status values for a backup or restore operation."""

from enum import StrEnum


class BackupStatus(StrEnum):
    """Status of a backup or restore operation.

    Follows the state machine defined in the backup data model:
    creating → completed|failed, completed → corrupted (on verify).
    """

    CREATING = "creating"
    COMPLETED = "completed"
    FAILED = "failed"
    CORRUPTED = "corrupted"
