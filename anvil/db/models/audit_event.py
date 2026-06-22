# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""AuditEvent ORM model — hash-chained event log.

Records every consequential lifecycle action in a verifiable,
append-only hash chain (FR-008-FR-013, FR-023). Each entry stores
the SHA-256 hash of the prior entry so that any insertion,
alteration, or deletion is detectable.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base
from ..timestamp_mixin import TimestampMixin


class AuditEvent(Base, TimestampMixin):
    """A single entry in the hash-chained audit trail.

    Maps to the ``audit_events`` table. Entries are **append-only**
    — no update or delete operations are exposed through the
    repository or service (VR-A3).

    Parameters
    ----------
    sequence : int
        Monotonic chain ordinal. Genesis entry has ``sequence=1``.
        Unique-indexed to prevent accidental duplicates.
    action_type : str
        Discriminator from ``AuditAction`` StrEnum (50 chars).
    target_type : str
        Discriminator from ``AuditTargetType`` StrEnum (50 chars).
    target_id : str or None
        Loose string reference to the target entity (avoids hard FK
        so audit entries survive entity deletion).
    actor : str
        Operating user/session or automated process name
        (e.g. ``"system:bootstrap"``).
    outcome : str
        Discriminator from ``AuditOutcome`` StrEnum (20 chars).
    reason : str or None
        Human-readable explanation, especially for rejections.
    params_json : str or None
        Canonical JSON of event parameters (references/summaries
        only — never full content bodies per FR-013).
    event_timestamp : datetime
        The action's timestamp (distinct from ``created_at`` which
        is the DB insert time).
    prev_hash : str
        Hex SHA-256 of the preceding entry. Genesis uses 64 zeros.
    entry_hash : str
        Hex SHA-256 over the canonical-JSON serialisation of this
        entry (including ``prev_hash``). Unique-indexed to detect
        duplicate inserts.
    """

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sequence: Mapped[int] = mapped_column(
        Integer, unique=True, nullable=False, index=True
    )
    action_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    target_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    params_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_timestamp: Mapped[datetime] = mapped_column(nullable=False)
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    entry_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
