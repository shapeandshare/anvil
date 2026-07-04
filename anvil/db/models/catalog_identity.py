# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""CatalogIdentity ORM entity for the import dedup guard."""

from __future__ import annotations

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base
from ..timestamp_mixin import TimestampMixin


class CatalogIdentity(Base, TimestampMixin):
    """Transactional dedup guard for external model imports.

    Each row records a unique identity triple
    ``(source_type, source_identifier, revision_sha)`` and the
    catalog model name + version it maps to.  The UNIQUE constraint on
    the identity triple prevents duplicate concurrent imports of the
    same exact revision (FR-005 / research D5).

    This is NOT a catalog mirror — it stores no metadata.  It is a
    transactional lock + triple-to-ModelRef resolution table, nothing
    more.

    Attributes
    ----------
    id : int
        Primary key, auto-increment.
    source_type : str
        Provider type (20 chars).
    source_identifier : str
        Provider-specific identifier (255 chars).
    revision_sha : str
        Provider revision SHA (255 chars).
    registry_model_name : str
        Catalog model name (255 chars).
    registry_model_version : int or None
        Catalog version, set after registration completes. ``None``
        while registration is in-flight.
    created_at : datetime
        TimestampMixin: row creation time.
    updated_at : datetime
        TimestampMixin: row last-update time.
    """

    __tablename__ = "catalog_identities"
    __table_args__ = (
        UniqueConstraint(
            "source_type",
            "source_identifier",
            "revision_sha",
            name="uq_catalog_identity_triple",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source_identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    revision_sha: Mapped[str] = mapped_column(String(255), nullable=False)
    registry_model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    registry_model_version: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )