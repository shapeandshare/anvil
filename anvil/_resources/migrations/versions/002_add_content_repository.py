"""Rev 002: Create content repository tables.

Creates the 10 content_* tables for the versioned Content Repository
(feature 016): content_sources, content_blobs, content_corpora,
content_versions, content_entries, content_tags,
content_ingest_sessions, content_import_jobs, content_locks,
and content_version_run_refs.

Handles the circular FK dependency between content_corpora and
content_versions by creating content_corpora first without the
current_version_id column, then adding it via batch_alter_table
after content_versions exists.
"""

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | None = None
depends_on: str | None = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    # ── 1. Content sources (no FK dependencies) ──────────────────────────
    op.create_table(
        "content_sources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(128), nullable=False),
        sa.Column("name", sa.String(255)),
        sa.Column("kind", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )

    # ── 2. Content blobs (no FK dependencies) ────────────────────────────
    op.create_table(
        "content_blobs",
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("content_hash"),
    )

    # ── 3. Content corpora (FK → license_catalog only; current_version_id  ─
    #    is added later after content_versions exists).
    op.create_table(
        "content_corpora",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(128), nullable=False),
        sa.Column("name", sa.String(255)),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column(
            "chunking_strategy", sa.String(20), nullable=False, server_default="windowed"
        ),
        sa.Column("block_size", sa.Integer(), nullable=False, server_default="16"),
        sa.Column("chunk_overlap", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column(
            "default_language", sa.String(16), nullable=False, server_default="en"
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("source_description", sa.String(1000), nullable=True),
        sa.Column(
            "license_id",
            sa.Integer(),
            sa.ForeignKey("license_catalog.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("attribution_text", sa.String(1000), nullable=True),
        sa.Column("origin", sa.String(20), nullable=False, server_default="user"),
        sa.Column("parent_provenance_ref", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )

    # ── 4. Content versions (FK → content_corpora) ───────────────────────
    op.create_table(
        "content_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "corpus_id",
            sa.Integer(),
            sa.ForeignKey("content_corpora.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("manifest_digest", sa.String(64)),
        sa.Column("label", sa.String(64), nullable=True),
        sa.Column("note", sa.String(1000), nullable=True),
        sa.Column("is_composition", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("entry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("corpus_id", "version_number"),
        sa.UniqueConstraint("corpus_id", "manifest_digest"),
    )

    # ── 5. Add current_version_id to content_corpora (batch mode for     ─
    #    SQLite compatibility).
    with op.batch_alter_table("content_corpora") as batch_op:
        batch_op.add_column(
            sa.Column(
                "current_version_id",
                sa.Integer(),
                sa.ForeignKey("content_versions.id", ondelete="SET NULL"),
                nullable=True,
            )
        )

    # ── 6. Content entries (FK → content_versions, content_sources) ──────
    op.create_table(
        "content_entries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "version_id",
            sa.Integer(),
            sa.ForeignKey("content_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("path", sa.String(1024)),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column(
            "source_id",
            sa.Integer(),
            sa.ForeignKey("content_sources.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_content_entries_version_path",
        "content_entries",
        ["version_id", "path"],
    )

    # ── 7. Content tags (FK → content_versions) ──────────────────────────
    op.create_table(
        "content_tags",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "version_id",
            sa.Integer(),
            sa.ForeignKey("content_versions.id", ondelete="CASCADE"),
        ),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("gc_protected", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version_id"),
        sa.UniqueConstraint("name"),
    )

    # ── 8. Ingest sessions (FK → content_corpora, content_sources,       ─
    #    content_versions).
    op.create_table(
        "content_ingest_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "corpus_id",
            sa.Integer(),
            sa.ForeignKey("content_corpora.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            sa.Integer(),
            sa.ForeignKey("content_sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("staging_key", sa.String(512), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("staged_entry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("problems_json", sa.Text(), nullable=True),
        sa.Column(
            "accepted_version_id",
            sa.Integer(),
            sa.ForeignKey("content_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("opened_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("staging_key"),
    )

    # ── 9. Import jobs (FK → content_corpora, content_sources,           ─
    #    content_ingest_sessions).
    op.create_table(
        "content_import_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "corpus_id",
            sa.Integer(),
            sa.ForeignKey("content_corpora.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            sa.Integer(),
            sa.ForeignKey("content_sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("config_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("content_ingest_sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("message", sa.String(1000), nullable=True),
        sa.Column("started_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── 10. Content locks (no FK dependencies) ───────────────────────────
    op.create_table(
        "content_locks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scope", sa.String(512)),
        sa.Column("holder", sa.String(256)),
        sa.Column("state", sa.String(20), nullable=False, server_default="held"),
        sa.Column("acquired_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("released_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── 11. Version run refs (FK → content_versions) ─────────────────────
    op.create_table(
        "content_version_run_refs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "version_id",
            sa.Integer(),
            sa.ForeignKey("content_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("mlflow_run_id", sa.String(64)),
        sa.Column("corpus_ref", sa.String(64)),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_content_version_run_refs_mlflow_run_id",
        "content_version_run_refs",
        ["mlflow_run_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_content_version_run_refs_mlflow_run_id",
        table_name="content_version_run_refs",
    )
    op.drop_table("content_version_run_refs")
    op.drop_table("content_locks")
    op.drop_table("content_import_jobs")
    op.drop_table("content_ingest_sessions")
    op.drop_table("content_tags")
    op.drop_index(
        "ix_content_entries_version_path", table_name="content_entries"
    )
    op.drop_table("content_entries")
    op.drop_table("content_versions")
    op.drop_table("content_corpora")
    op.drop_table("content_blobs")
    op.drop_table("content_sources")
