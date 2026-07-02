# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""TeachingSession ORM model for the interactive teaching loop.

This module defines the ``TeachingSession`` model, which represents an
ordered chain of teaching rounds over a model. Unlike other model
references in the codebase, ``TeachingSession`` does **not** use an
``ExternalModel`` FK — it chains on the native integer experiment id
(the identifier that warm-start and ``InferenceService.load_model()``
already agree on).
"""

from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base
from ..timestamp_mixin import TimestampMixin
from .teaching_session_status import TeachingSessionStatus


class TeachingSession(Base, TimestampMixin):
    """A teaching session — an ordered chain of chained training rounds.

    Maps to the ``teaching_sessions`` table. The session row acts as
    the **chain head**, holding ``current_base_experiment_id`` so the
    next round can warm-start from it. Round lineage lives in MLflow
    tags; the session row is the authoritative pointer for "next base."

    Mapped columns
    --------------
    id : int
        Primary key, auto-increment.
    name : str
        User-facing session name (255 chars max).
    description : str or None
        Optional human-readable description (1000 chars max).
    seed_experiment_id : int or None
        Experiment id the session started from (null = train from scratch
        in round 1). Provenance only.
    current_base_experiment_id : int or None
        Experiment id the next round warm-starts from. Updated ONLY after
        a round's training finalization succeeds.
    status : str
        Lifecycle status — one of ``TeachingSessionStatus`` values
        (default ``DRAFT``, 16 chars max).
    """

    __tablename__ = "teaching_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    seed_experiment_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_base_experiment_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), default=TeachingSessionStatus.DRAFT)
