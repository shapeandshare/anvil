# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Instance record ORM for the global host-level instance registry.

Stored in its own SQLite database at ``~/.anvil/registry.db`` (not in
a per-instance app DB).  Enforces four unique constraints — one per
row — so ``INSERT`` with a duplicte name, workspace, or port raises
an integrity error that is caught by ``InstanceRegistryRepository``
and surfaced as a specific collision message.

Mapped columns
--------------
id : int
    Primary key, auto-increment.
name : str
    Instance identifier, caller-provided, required, unique, indexed.
workspace_root : str
    Absolute path to the instance's workspace root directory. Unique.
web_port : int
    Web/uvicorn port. Unique across all instances.
mlflow_port : int
    MLflow sidecar port. Unique across all instances.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base
from ..timestamp_mixin import TimestampMixin


class InstanceRecord(Base, TimestampMixin):
    """A registered instance in the global host-level registry."""

    __tablename__ = "instance_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False
    )
    workspace_root: Mapped[str] = mapped_column(
        String(500), unique=True, nullable=False
    )
    web_port: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    mlflow_port: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
