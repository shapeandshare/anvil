"""Rev 004: Add curation tables (samples, curation_operations, import_sources) and extend datasets."""

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    # Extend datasets table with curation fields
    op.add_column("datasets", sa.Column("sample_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("datasets", sa.Column("total_size_bytes", sa.Integer(), server_default="0", nullable=False))
    op.add_column("datasets", sa.Column("curation_version", sa.Integer(), server_default="0", nullable=False))
    op.add_column("datasets", sa.Column("status", sa.String(20), server_default="empty", nullable=False))

    # Create import_sources table (referenced by samples FK)
    op.create_table(
        "import_sources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("format", sa.String(20), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create curation_operations table (referenced by samples.removed_by_op_id FK)
    op.create_table(
        "curation_operations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("operation_type", sa.String(50), nullable=False),
        sa.Column("parameters", sa.Text(), nullable=True),
        sa.Column("sample_count_before", sa.Integer(), nullable=False),
        sa.Column("sample_count_after", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create samples table
    op.create_table(
        "samples",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("index", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("length", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("is_removed", sa.Boolean(), server_default="0", nullable=False, index=True),
        sa.Column("removed_by_op_id", sa.Integer(), sa.ForeignKey("curation_operations.id"), nullable=True),
        sa.Column("import_source_id", sa.Integer(), sa.ForeignKey("import_sources.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create composite indexes for samples
    op.create_index("ix_samples_dataset_index", "samples", ["dataset_id", "index"])
    op.create_index("ix_samples_dataset_hash", "samples", ["dataset_id", "content_hash"])
    op.create_index("ix_samples_dataset_length", "samples", ["dataset_id", "length"])


def downgrade():
    op.drop_index("ix_samples_dataset_length", table_name="samples")
    op.drop_index("ix_samples_dataset_hash", table_name="samples")
    op.drop_index("ix_samples_dataset_index", table_name="samples")
    op.drop_table("samples")
    op.drop_table("curation_operations")
    op.drop_table("import_sources")
    op.drop_column("datasets", "status")
    op.drop_column("datasets", "curation_version")
    op.drop_column("datasets", "total_size_bytes")
    op.drop_column("datasets", "sample_count")