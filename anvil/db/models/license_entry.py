"""LicenseEntry ORM model — the approved-license catalog.

Stores the set of recognized/approved licenses under which bundled
sample data may be accepted and redistributed (FR-002). Each entry
carries metadata for attribution compliance (FR-006).
"""

from __future__ import annotations

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base
from ..timestamp_mixin import TimestampMixin


class LicenseEntry(Base, TimestampMixin):
    """A single entry in the approved-license catalog.

    Maps to the ``license_catalog`` table.

    Parameters
    ----------
    identifier : str
        Unique license identifier (e.g. ``"MIT"``, ``"CC-BY-4.0"``,
        ``"Public Domain"``, ``"own-content"``).
    display_name : str
        Human-readable license name.
    requires_attribution : bool
        Whether this license requires attribution when content is
        displayed, exported, or used for training (FR-006).
        Defaults to ``False``.
    redistribution_allowed : bool
        Whether the data may be redistributed.  The ``own-content``
        sentinel sets this to ``False``.  Defaults to ``True``.
    is_own_content_sentinel : bool
        ``True`` only for the single ``own-content`` row that exempts
        user-provided data from the approved-list requirement.
        Defaults to ``False``.
    """

    __tablename__ = "license_catalog"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    identifier: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    requires_attribution: Mapped[bool] = mapped_column(Boolean, default=False)
    redistribution_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    is_own_content_sentinel: Mapped[bool] = mapped_column(Boolean, default=False)