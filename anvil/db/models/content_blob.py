# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""ContentBlob ORM model — content-addressed blob metadata.

Tracks the size of each unique content blob in the repository.
Actual blob content is stored content-addressed on the filesystem;
this table records the mapping from hash to size for GC and
statistics.
"""

from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base
from ..timestamp_mixin import TimestampMixin


class ContentBlob(Base, TimestampMixin):
    """Metadata for a content-addressed blob.

    Maps to the ``content_blobs`` table.  The primary key is the
    SHA-256 hex digest of the blob content, enabling deduplication:
    entries with the same content hash share a single row.  Actual
    binary content is stored on the filesystem, keyed by hash.

    Parameters
    ----------
    content_hash : str
        SHA-256 hex digest of the blob content (64 chars). Primary key.
    size_bytes : int
        Blob size in bytes.
    """

    __tablename__ = "content_blobs"

    content_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
