# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""CheckoutLock ORM model — advisory checkout lock.

Advisory locks prevent concurrent modification of content scopes
(such as a corpus or version) during checkout and merge operations.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ...services.content.lock_state import LockState
from ..base import Base
from ..timestamp_mixin import TimestampMixin


class CheckoutLock(Base, TimestampMixin):
    """An advisory content checkout lock.

    Maps to the ``content_locks`` table.  Each row represents an
    advisory lock on a content scope (e.g. a corpus or version).
    Locks are acquired and released by content operations to prevent
    concurrent modification.

    Parameters
    ----------
    scope : str
        Lock scope identifier (512 chars max), e.g. ``"corpus:42"``.
    holder : str
        Lock holder identifier (256 chars max).
    state : str
        Lock state from ``LockState``, default ``LockState.HELD``.
    acquired_at : datetime
        Timestamp when the lock was acquired (server default now).
    released_at : datetime or None
        Timestamp when the lock was released.
    """

    __tablename__ = "content_locks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(512))
    holder: Mapped[str] = mapped_column(String(256))
    state: Mapped[str] = mapped_column(String(20), default=LockState.HELD)
    acquired_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    released_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
