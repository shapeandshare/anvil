# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Manifest embedded in every backup archive for integrity verification."""

from datetime import datetime

from pydantic import BaseModel

from .manifest_entry import ManifestEntry


class BackupManifest(BaseModel):
    """Metadata and integrity data embedded at the root of each archive.

    The manifest is written as ``manifest.json`` inside the archive and
    is the first member, immediately followed by every file it describes.

    Parameters
    ----------
    manifest_version : int
        Format version for forward-compatibility checks.
    backup_id : str
        Unique backup identifier.
    created_at : datetime
        UTC timestamp of creation.
    operation_type : str
        ``backup`` or ``pre_restore_safety``.
    deployment_version : str
        Value of ``anvil.__version__`` at creation time.
    schema_revision : str
        Alembic head revision at creation time.
    total_uncompressed_bytes : int
        Summed size of all ``entries`` before compression.
    entries : list[ManifestEntry]
        One entry per archived file except ``manifest.json`` itself.
    """

    manifest_version: int = 1
    backup_id: str
    created_at: datetime
    operation_type: str
    deployment_version: str
    schema_revision: str
    total_uncompressed_bytes: int
    entries: list[ManifestEntry]

    class Config:
        extra = "ignore"  # forward-compat: ignore unknown fields
