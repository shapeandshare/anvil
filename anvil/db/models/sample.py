# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Sample ORM model for individual training samples within a dataset.

This module defines the ``Sample`` model, which represents a single
training sample (a tokenized text segment) belonging to a dataset.
Samples track content hashes for deduplication and support soft-deletion
via the ``is_removed`` flag during curation.
"""

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base
from ..timestamp_mixin import TimestampMixin


class Sample(Base, TimestampMixin):
    """A single training sample within a dataset.

    Maps to the ``samples`` table. Each row represents an individual
    training example belonging to a dataset. Samples track content
    hashes for deduplication and support soft-deletion via the
    ``is_removed`` flag during curation. Composite indexes on
    ``(dataset_id, index)``, ``(dataset_id, content_hash)``, and
    ``(dataset_id, length)`` optimize query performance.

    Mapped columns
    --------------
    id : int
        Primary key, auto-increment.
    dataset_id : int
        Foreign key to ``datasets.id`` (CASCADE on delete), indexed.
    index : int
        Positional index of this sample within the dataset.
    content_hash : str
        SHA-256 (or similar) hash for deduplication (64 chars).
    length : int
        Length of the sample in tokens or characters.
    file_path : str
        Path to the file containing this sample's content.
    is_removed : bool
        Soft-delete flag for curation (default ``False``), indexed.
    removed_by_op_id : int or None
        Foreign key to ``curation_operations.id``, set when removed.
    import_source_id : int or None
        Foreign key to ``import_sources.id``, recording the source.

    Table args
    ----------
    __table_args__ : tuple
        Composite indexes on ``(dataset_id, index)``,
        ``(dataset_id, content_hash)``, and
        ``(dataset_id, length)``.
    """

    __tablename__ = "samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    index: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    length: Mapped[int] = mapped_column(Integer, nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    is_removed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    removed_by_op_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("curation_operations.id"), nullable=True
    )
    import_source_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("import_sources.id"), nullable=True
    )

    __table_args__ = (
        Index("ix_samples_dataset_index", "dataset_id", "index"),
        Index("ix_samples_dataset_hash", "dataset_id", "content_hash"),
        Index("ix_samples_dataset_length", "dataset_id", "length"),
    )
