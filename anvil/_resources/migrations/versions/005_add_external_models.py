"""Rev 005: Create external_models and model_import_jobs tables.

Creates the ``external_models`` table for tracking externally-sourced
model metadata and the ``model_import_jobs`` table for async import
job lifecycle (feature 040).
"""

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | None = None
depends_on: str | None = None

import sqlalchemy as sa
from alembic import op


def upgrade() -> None:
    op.create_table(
        "external_models",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("source_identifier", sa.String(255), nullable=False),
        sa.Column("architecture_family", sa.String(100), nullable=False),
        sa.Column("parameter_count", sa.Integer(), nullable=False),
        sa.Column("license", sa.String(100), nullable=False),
        sa.Column("tokenizer_family", sa.String(100), nullable=False),
        sa.Column("revision_sha", sa.String(255), nullable=False),
        sa.Column("runnable_status", sa.String(20), nullable=False),
        sa.Column("runnable_reason", sa.Text(), nullable=True),
        sa.Column("asset_availability", sa.String(20), nullable=False),
        sa.Column("config_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "model_import_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("source_identifier", sa.String(255), nullable=False),
        sa.Column("revision", sa.String(255), nullable=False),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "external_model_id",
            sa.Integer(),
            sa.ForeignKey("external_models.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_model_import_jobs_status", "model_import_jobs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_model_import_jobs_status", table_name="model_import_jobs")
    op.drop_table("model_import_jobs")
    op.drop_table("external_models")
