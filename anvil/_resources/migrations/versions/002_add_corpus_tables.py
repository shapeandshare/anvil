"""Rev 002: Create corpus and corpus_files tables."""

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None

import sqlalchemy as sa
from alembic import op


def upgrade():
    op.create_table(
        "corpora",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("root_path", sa.String(500), nullable=False),
        sa.Column("include_patterns", sa.Text(), nullable=True),
        sa.Column("exclude_patterns", sa.Text(), nullable=True),
        sa.Column(
            "chunking_strategy",
            sa.String(20),
            nullable=False,
            server_default="windowed",
        ),
        sa.Column("chunk_overlap", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("file_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("document_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("language_map", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "corpus_files",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "corpus_id",
            sa.Integer(),
            sa.ForeignKey("corpora.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relative_path", sa.String(1000), nullable=False),
        sa.Column("language", sa.String(50), nullable=True),
        sa.Column("line_count", sa.Integer(), nullable=True),
        sa.Column("char_count", sa.Integer(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=True),
        sa.Column("encoding", sa.String(20), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("last_modified", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("corpus_id", "relative_path"),
    )


def downgrade():
    op.drop_table("corpus_files")
    op.drop_table("corpora")
