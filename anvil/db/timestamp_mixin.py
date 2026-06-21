# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Common timestamp mixin for ORM models."""

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    """Mixin adding ``created_at`` and ``updated_at`` timestamp columns.

    Intended for multiple inheritance with :class:`anvil.db.base.Base`.
    Provides automatic timestamping on row creation and update.

    Attributes
    ----------
    created_at : Mapped[datetime]
        Timestamp set once when the row is first inserted. Uses the
        database server's ``now()`` via ``server_default``.
    updated_at : Mapped[datetime]
        Timestamp set on insert and automatically refreshed on every
        subsequent update via ``onupdate=func.now()``.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
