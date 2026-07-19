"""Rev 015: Add feedback_reports and feedback_annotations tables.

Creates the ``feedback_reports`` and ``feedback_annotations`` tables
for the Visual Feedback Annotation feature (spec 001). Each report
captures a page screenshot at a given viewport size, and carries zero
or more annotations (element, circle, or freehand).

Greenfield — no pre-existing data requiring a backfill.

Revision ID: 015_add_feedback_reports
Revises: 014_add_download_job_source_columns
Create Date: 2026-07-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "015_add_feedback_reports"
down_revision: str | None = "014_add_download_job_source_columns"
branch_labels: str | None = None
depends_on: str | None = None

_CURRENT_TS = sa.text("(CURRENT_TIMESTAMP)")
"""Reusable default for created_at / updated_at columns."""


def upgrade() -> None:
    """Create the ``feedback_reports`` and ``feedback_annotations``
    tables."""
    op.create_table(
        "feedback_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("page_url", sa.String(512), nullable=False),
        sa.Column("viewport_width", sa.Integer(), nullable=False),
        sa.Column("viewport_height", sa.Integer(), nullable=False),
        sa.Column("screenshot_path", sa.String(512), nullable=True),
        sa.Column("annotated_path", sa.String(512), nullable=True),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'open'"),
        ),
        sa.Column(
            "reporter_id",
            sa.String(255),
            nullable=False,
            server_default=sa.text("'default'"),
        ),
        sa.Column("notes_summary", sa.String(1000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=_CURRENT_TS,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=_CURRENT_TS,
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_feedback_reports")),
    )
    op.create_index(
        "idx_feedback_reports_status",
        "feedback_reports",
        ["status"],
    )
    op.create_index(
        "idx_feedback_reports_created",
        "feedback_reports",
        ["created_at"],
    )

    op.create_table(
        "feedback_annotations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("report_id", sa.Integer(), nullable=False),
        sa.Column("annotation_type", sa.String(16), nullable=False),
        sa.Column("note", sa.String(2000), nullable=True),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=_CURRENT_TS,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=_CURRENT_TS,
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_feedback_annotations")),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["feedback_reports.id"],
            name=op.f("fk_feedback_annotations_report_id"),
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "idx_feedback_annotations_report",
        "feedback_annotations",
        ["report_id"],
    )


def downgrade() -> None:
    """Drop the ``feedback_annotations`` and ``feedback_reports`` tables
    and their indexes."""
    op.drop_index("idx_feedback_annotations_report", table_name="feedback_annotations")
    op.drop_table("feedback_annotations")
    op.drop_index("idx_feedback_reports_created", table_name="feedback_reports")
    op.drop_index("idx_feedback_reports_status", table_name="feedback_reports")
    op.drop_table("feedback_reports")
