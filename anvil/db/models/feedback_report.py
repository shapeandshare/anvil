# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.
# one-class:allow — bidirectional ORM relationship() cycle between
# FeedbackReport ↔ FeedbackAnnotation; merging is the constitution-
# prescribed resolution for co-dependent model classes (Article VI).

"""FeedbackReport and FeedbackAnnotation ORM models.

Both models are defined in a single module to eliminate circular import
cycles between their bidirectional ``relationship()`` declarations
(per the ``__init__.py`` Ownership Policy — co-dependent classes in one
file).
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base
from ..timestamp_mixin import TimestampMixin


class FeedbackReport(Base, TimestampMixin):
    """A visual feedback report capturing page screenshots and metadata.

    Maps to the ``feedback_reports`` table. Each report captures a page
    at a given viewport size and carries zero or more annotations.

    Mapped columns
    --------------
    id : int
        Primary key, auto-increment.
    page_url : str
        URL of the page being reviewed (512 chars max).
    viewport_width : int
        Browser viewport width in pixels at capture time.
    viewport_height : int
        Browser viewport height in pixels at capture time.
    screenshot_path : str or None
        Path to the raw screenshot file (512 chars max).
    annotated_path : str or None
        Path to the annotated screenshot file (512 chars max).
    status : str
        Lifecycle status — one of ``FeedbackStatus`` values
        (default ``"open"``, 16 chars max).
    reporter_id : str
        Identifier of the person who submitted the report
        (default ``"default"``, 255 chars max).
    notes_summary : str or None
        Optional summary text for the report (1000 chars max).
    """

    __tablename__ = "feedback_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    page_url: Mapped[str] = mapped_column(String(512))
    viewport_width: Mapped[int] = mapped_column(Integer)
    viewport_height: Mapped[int] = mapped_column(Integer)
    screenshot_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    annotated_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="open")
    reporter_id: Mapped[str] = mapped_column(String(255), default="default")
    notes_summary: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    annotations: Mapped[list[FeedbackAnnotation]] = relationship(
        "FeedbackAnnotation",
        back_populates="report",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class FeedbackAnnotation(Base, TimestampMixin):
    """A single annotation on a feedback report.

    Maps to the ``feedback_annotations`` table. Each annotation belongs
    to exactly one ``FeedbackReport`` and describes a visual markup —
    a highlighted element, a drawn circle, or a freehand path — together
    with an optional note.

    Mapped columns
    --------------
    id : int
        Primary key, auto-increment.
    report_id : int
        Foreign key to ``feedback_reports.id``; cascade delete.
    annotation_type : str
        Type of annotation — one of ``AnnotationType`` values
        (16 chars max).
    note : str or None
        Optional human-readable note (2000 chars max).
    data : str
        JSON blob containing the annotation geometry and payload.
    order : int
        Display ordering within the report (default ``0``).
    """

    __tablename__ = "feedback_annotations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("feedback_reports.id", ondelete="CASCADE"), nullable=False
    )
    annotation_type: Mapped[str] = mapped_column(String(16))
    note: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    data: Mapped[str] = mapped_column(Text)
    order: Mapped[int] = mapped_column(Integer, default=0)

    report: Mapped[FeedbackReport] = relationship(
        "FeedbackReport", back_populates="annotations"
    )
