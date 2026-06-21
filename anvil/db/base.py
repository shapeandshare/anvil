# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""SQLAlchemy declarative base with common mixins."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base class for all anvil ORM models.

    All table-mapped models inherit from this class rather than
    ``DeclarativeBase`` directly, providing a single registry for
    metadata, table creation, and Alembic autogeneration.
    """
