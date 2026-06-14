"""Merge 002b and 006 heads."""

revision: str = "12a4027155f0"
down_revision: tuple[str, str] = ("002b", "006")
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
