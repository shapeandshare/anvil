# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""CurationOperation ORM model for tracking dataset curation actions.

This module defines the ``CurationOperation`` model, which records
individual curation operations performed on datasets (e.g., deduplication,
filtering, or transformation). Each operation logs the before-and-after
sample count to enable audit trails and rollback analysis.
"""

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base
from ..timestamp_mixin import TimestampMixin


class CurationOperation(Base, TimestampMixin):
    """A curation operation performed on a dataset.

    Maps to the ``curation_operations`` table. Each row records a
    single curation action (e.g., deduplication, filtering,
    transformation) applied to a dataset, logging the operation
    type, parameters, and the sample counts before and after
    the operation for audit trail purposes.

    Mapped columns
    --------------
    id : int
        Primary key, auto-increment.
    dataset_id : int
        Foreign key to ``datasets.id`` (CASCADE on delete), indexed.
    operation_type : str
        Type of curation operation (50 chars max).
    parameters : str or None
        JSON-encoded operation parameters (text blob).
    sample_count_before : int
        Number of samples in the dataset before this operation.
    sample_count_after : int
        Number of samples in the dataset after this operation.
    """

    __tablename__ = "curation_operations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    operation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    parameters: Mapped[str | None] = mapped_column(Text, nullable=True)
    sample_count_before: Mapped[int] = mapped_column(Integer, nullable=False)
    sample_count_after: Mapped[int] = mapped_column(Integer, nullable=False)
