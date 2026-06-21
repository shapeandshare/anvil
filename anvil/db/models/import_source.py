# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""ImportSource ORM model for dataset import source files.

This module defines the ``ImportSource`` model, which records the
origin of imported dataset samples. Each import source tracks the
source filename, format, row count, and error count for a given
dataset.
"""

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base
from ..timestamp_mixin import TimestampMixin


class ImportSource(Base, TimestampMixin):
    """A source file from which dataset samples were imported.

    Maps to the ``import_sources`` table. Each row records the origin
    of imported samples for a dataset, including the source filename,
    file format, total row count, and number of errors encountered
    during import.

    Mapped columns
    --------------
    id : int
        Primary key, auto-increment.
    dataset_id : int
        Foreign key to ``datasets.id`` (CASCADE on delete), indexed.
    filename : str
        Source filename (500 chars max).
    format : str
        File format (e.g., ``"txt"``, ``"jsonl"``; 20 chars max).
    row_count : int
        Number of rows imported from this source (default ``0``).
    error_count : int
        Number of errors encountered during import (default ``0``).
    """

    __tablename__ = "import_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
