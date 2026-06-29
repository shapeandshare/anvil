"""Rev 006: Create chat_templates and fine_tune_datasets tables.

Creates the ``chat_templates`` table for tracking chat templates (the
Jinja-like template strings that render prompts/responses for fine-tuning)
and the ``fine_tune_datasets`` table for tracking prepared SFT/preference
datasets as first-class, versioned entities (spec 053).
"""

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "chat_templates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("template_string", sa.Text(), nullable=False),
        sa.Column("tokenizer_family", sa.String(20), nullable=False),
        sa.Column(
            "base_model_ref",
            sa.Integer(),
            sa.ForeignKey("external_models.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("description", sa.Text(), nullable=True),
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
        sa.UniqueConstraint("name"),
    )
    op.create_index(
        "ix_chat_templates_base_model_ref",
        "chat_templates",
        ["base_model_ref"],
    )
    op.create_index(
        "ix_chat_templates_tokenizer_family_status",
        "chat_templates",
        ["tokenizer_family", "status"],
    )

    op.create_table(
        "fine_tune_datasets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "dataset_id",
            sa.Integer(),
            sa.ForeignKey("datasets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "chat_template_id",
            sa.Integer(),
            sa.ForeignKey("chat_templates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "base_model_ref",
            sa.Integer(),
            sa.ForeignKey("external_models.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="preparing",
        ),
        sa.Column("record_type", sa.String(20), nullable=False),
        sa.Column("summary_json", sa.Text(), nullable=True),
        sa.Column("prepared_file_path", sa.String(500), nullable=True),
        sa.Column("record_count", sa.Integer(), nullable=False, server_default="0"),
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
    op.create_index(
        "ix_fine_tune_datasets_dataset_id_status",
        "fine_tune_datasets",
        ["dataset_id", "status"],
    )
    op.create_index(
        "ix_fine_tune_datasets_status",
        "fine_tune_datasets",
        ["status"],
    )
    op.create_index(
        "ix_fine_tune_datasets_base_model_ref",
        "fine_tune_datasets",
        ["base_model_ref"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_fine_tune_datasets_base_model_ref",
        table_name="fine_tune_datasets",
    )
    op.drop_index(
        "ix_fine_tune_datasets_status",
        table_name="fine_tune_datasets",
    )
    op.drop_index(
        "ix_fine_tune_datasets_dataset_id_status",
        table_name="fine_tune_datasets",
    )
    op.drop_table("fine_tune_datasets")
    op.drop_index(
        "ix_chat_templates_tokenizer_family_status",
        table_name="chat_templates",
    )
    op.drop_index(
        "ix_chat_templates_base_model_ref",
        table_name="chat_templates",
    )
    op.drop_table("chat_templates")
