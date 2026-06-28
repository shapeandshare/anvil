# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Per-instance runtime configuration overrides.

Stored in the per-instance app database (``data/anvil-state.db`` in
the instance's workspace).  Each row is a single key/value override
with an ``apply_class`` describing how it takes effect.

Boot-critical values (workspace root, web port, MLflow port, DB path)
live in the workspace ``instance.json`` boot file — they are NOT
stored in this table.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ...db.base import Base
from ...db.timestamp_mixin import TimestampMixin


class RuntimeConfig(Base, TimestampMixin):
    """A persisted runtime configuration override for one setting."""

    __tablename__ = "runtime_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False
    )
    value: Mapped[str] = mapped_column(Text, nullable=False)
    apply_class: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
