# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""VersionRunRef ORM model — MLflow run ↔ version linkage.

Records which MLflow training runs used which version of a corpus,
enabling experiment lineage to be traced back to the exact content
snapshot.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base
from ..timestamp_mixin import TimestampMixin


class VersionRunRef(Base, TimestampMixin):
    """Link between an MLflow run and a content version.

    Maps to the ``content_version_run_refs`` table.  Each row
    associates an MLflow training run with the exact content version
    snapshot it consumed, so that experiments can be reproduced
    deterministically.

    Parameters
    ----------
    version_id : int
        FK to ``content_versions.id`` (CASCADE on delete).
    mlflow_run_id : str
        MLflow run UUID (64 chars max). Indexed for fast lookup.
    corpus_ref : str
        Corpus reference string (64 chars max), typically
        ``"corpus:<slug>"`` or ``"corpus:<id>"`` for denormalised
        quick access.
    """

    __tablename__ = "content_version_run_refs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("content_versions.id", ondelete="CASCADE"), nullable=False
    )
    mlflow_run_id: Mapped[str] = mapped_column(String(64), index=True)
    corpus_ref: Mapped[str] = mapped_column(String(64))
