"""Rev 003: Create backup_operations table.

Creates the ``backup_operations`` table for the full-deployment backup
& restore feature (feature 026). Tracks backup, restore, and
pre-restore-safety operations with status, manifest metadata, schema
revision, and audit fields.
"""

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | None = None
depends_on: str | None = None

import sqlalchemy as sa
from alembic import op


def upgrade() -> None:
    op.create_table(
        "backup_operations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("backup_id", sa.String(64), nullable=False),
        sa.Column("operation_type", sa.String(20), nullable=False, server_default="backup"),
        sa.Column("status", sa.String(20), nullable=False, server_default="creating"),
        sa.Column("archive_filename", sa.String(255), nullable=True),
        sa.Column("archive_size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_uncompressed_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("manifest_sha256", sa.String(64), nullable=True),
        sa.Column("deployment_version", sa.String(50), nullable=True),
        sa.Column("schema_revision", sa.String(64), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("restored_from_backup_id", sa.String(64), nullable=True),
        sa.Column("safety_snapshot_id", sa.String(64), nullable=True),
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
        sa.UniqueConstraint("backup_id"),
    )
    op.create_index("ix_backup_operations_backup_id", "backup_operations", ["backup_id"])
    op.create_index("ix_backup_operations_status", "backup_operations", ["status"])
    op.create_index(
        "ix_backup_operations_created_at", "backup_operations", ["created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_backup_operations_backup_id", table_name="backup_operations")
    op.drop_index("ix_backup_operations_status", table_name="backup_operations")
    op.drop_index("ix_backup_operations_created_at", table_name="backup_operations")
    op.drop_table("backup_operations")