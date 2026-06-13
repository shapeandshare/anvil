"""Rev 002b: Add model registry tables."""

revision = "002b"
down_revision = "002"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "registered_models" not in inspector.get_table_names():
        op.create_table(
            "registered_models",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("name", sa.String(255), nullable=False, unique=True),
            sa.Column("description", sa.String(1000), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    if "model_versions" not in inspector.get_table_names():
        op.create_table(
            "model_versions",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("model_id", sa.Integer(), sa.ForeignKey("registered_models.id"), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("experiment_id", sa.Integer(), sa.ForeignKey("experiments.id"), nullable=False),
            sa.Column("dataset_name", sa.String(255), nullable=True),
            sa.Column("artifact_path", sa.String(500), nullable=False),
            sa.Column("final_loss", sa.Float(), nullable=True),
            sa.Column("hyperparameters_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("model_id", "version"),
        )


def downgrade():
    op.drop_table("model_versions")
    op.drop_table("registered_models")