"""SQLAlchemy declarative base with common mixins."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base class for all anvil ORM models.

    All table-mapped models inherit from this class rather than
    ``DeclarativeBase`` directly, providing a single registry for
    metadata, table creation, and Alembic autogeneration.
    """
