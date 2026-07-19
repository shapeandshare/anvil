"""Rev 016: Add document_title and user_agent to feedback_reports.

Adds two metadata columns to the ``feedback_reports`` table so that
coding agents can understand the document context and browser
environment when processing submitted feedback reports.

Revision ID: 016_add_feedback_report_metadata
Revises: 015_add_feedback_reports
Create Date: 2026-07-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "016_add_feedback_report_metadata"
down_revision: str | None = "015_add_feedback_reports"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Add ``document_title`` and ``user_agent`` columns."""
    op.add_column(
        "feedback_reports",
        sa.Column("document_title", sa.String(512), nullable=True),
    )
    op.add_column(
        "feedback_reports",
        sa.Column("user_agent", sa.String(512), nullable=True),
    )


def downgrade() -> None:
    """Drop the two metadata columns."""
    op.drop_column("feedback_reports", "user_agent")
    op.drop_column("feedback_reports", "document_title")
