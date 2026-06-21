# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Dataset ORM model for uploaded training datasets.

This module defines the ``Dataset`` model, which represents a training
dataset that has been uploaded or imported into the anvil system. Each
dataset tracks metadata such as file path, vocabulary size, document
count, curation state, and sample statistics.
"""

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ...services.datasets.dataset_status import DatasetStatus
from ..base import Base
from ..timestamp_mixin import TimestampMixin


class Dataset(Base, TimestampMixin):
    """A training dataset uploaded or imported into the system.

    Maps to the ``datasets`` table. Each row represents a training
    dataset with metadata about its source file, vocabulary size,
    document count, curation version, and processing status.

    Mapped columns
    --------------
    id : int
        Primary key, auto-increment.
    name : str
        Unique dataset name (255 chars max).
    description : str or None
        Optional human-readable description (1000 chars max).
    filename : str
        Original source filename (255 chars max).
    file_path : str
        Filesystem path to the dataset file (500 chars max).
    vocabulary_size : int or None
        Number of unique tokens in the dataset.
    document_count : int or None
        Number of individual documents/records.
    is_default : bool
        Whether this is the default dataset (default ``False``).
    sample_count : int
        Number of individual training samples (default ``0``).
    total_size_bytes : int
        Total dataset size in bytes (default ``0``).
    curation_version : int
        Monotonically increasing curation version number (default ``0``).
    status : str
        Processing status (default ``DatasetStatus.EMPTY``, 20 chars max).
    """

    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    filename: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(500))
    vocabulary_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    document_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    total_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    curation_version: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default=DatasetStatus.EMPTY)
    # Provenance fields.
    source_description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    license_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("license_catalog.id", ondelete="RESTRICT"), nullable=True
    )
    attribution_text: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    origin: Mapped[str] = mapped_column(String(20), default="user")
    parent_provenance_ref: Mapped[int | None] = mapped_column(Integer, nullable=True)
