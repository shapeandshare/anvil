# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Preview data shown before a restore is confirmed."""

from datetime import datetime

from pydantic import BaseModel


class RestorePreview(BaseModel):
    """Read-only summary shown on restore-wizard step 1.

    Parameters
    ----------
    backup_id : str
    created_at : datetime
    archive_size_bytes : int
    total_uncompressed_bytes : int
    entry_count : int
        Number of files in the archive.
    deployment_version : str
        From the backup manifest.
    schema_revision : str
        From the backup manifest.
    compatibility : str
        ``ok``, ``warn``, or ``blocked``.
    compatibility_detail : str
        Human-readable explanation of the compat result.
    required_free_bytes : int
        Estimated space needed for safety snapshot + extraction.
    sufficient_space : bool
        Whether the pre-flight check passed.
    """

    backup_id: str
    created_at: datetime
    archive_size_bytes: int = 0
    total_uncompressed_bytes: int = 0
    entry_count: int = 0
    deployment_version: str = ""
    schema_revision: str = ""
    compatibility: str = "ok"
    compatibility_detail: str = ""
    required_free_bytes: int = 0
    sufficient_space: bool = True
