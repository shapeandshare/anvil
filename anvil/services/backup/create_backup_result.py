# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Return type for BackupService.create_backup, carrying rotation info."""

from pydantic import BaseModel


class CreateBackupResult(BaseModel):
    """Result of a ``create_backup`` call, including auto-rotation data.

    The route handler uses ``rotated_backup_ids`` to emit one
    ``backup_delete`` audit event per rotated backup (research R11).

    Parameters
    ----------
    backup_id : str
        The newly created backup identifier.
    rotated_backup_ids : list[str]
        Identifiers of non-safety backups that were auto-deleted to
        stay within the storage quota.
    """

    backup_id: str
    rotated_backup_ids: list[str] = []
