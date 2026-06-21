# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""ContentSource ORM model — categorised content origin.

Each row represents a content source (ingestor, importer, or manual)
from which content is ingested into the repository.
"""

from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ...services.content.source_kind import SourceKind
from ..base import Base
from ..timestamp_mixin import TimestampMixin


class ContentSource(Base, TimestampMixin):
    """A categorised content origin.

    Maps to the ``content_sources`` table. Each source represents a
    well-known origin for content ingested into a corpus, carrying
    a ``kind`` discriminator from :class:`SourceKind`.

    Parameters
    ----------
    slug : str
        Unique machine-readable identifier (128 chars max).
    name : str
        Human-readable source name (255 chars max).
    kind : str
        Source category from ``SourceKind`` (20 chars max).
        Defaults to ``SourceKind.MANUAL``.
    """

    __tablename__ = "content_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(20), default=SourceKind.MANUAL)
