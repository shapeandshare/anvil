"""Rev 014: Add source_identifier and revision to asset_download_jobs.

The ``external_models`` table was dropped in Rev 013 (SC-006 / FR-007).
The download pipeline previously depended on ``ExternalModel`` rows to
resolve the HF source identifier and revision for downloads.  This
migration adds those fields directly to the ``asset_download_jobs``
table so the background worker can read them without any
``ExternalModel`` table lookup.

Revision ID: 014_add_download_job_source_columns
Revises: 013_drop_external_models
Create Date: 2026-07-05
"""

revision: str = "014_add_download_job_source_columns"
down_revision: str | None = "013_drop_external_models"
branch_labels: str | None = None
depends_on: str | None = None

import sqlalchemy as sa
from alembic import op


def upgrade() -> None:
    with op.batch_alter_table("asset_download_jobs") as batch_op:
        batch_op.add_column(
            sa.Column("source_identifier", sa.String(255), nullable=True)
        )
        batch_op.add_column(sa.Column("revision", sa.String(255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("asset_download_jobs") as batch_op:
        batch_op.drop_column("revision")
        batch_op.drop_column("source_identifier")
