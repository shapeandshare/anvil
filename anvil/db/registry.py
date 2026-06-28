# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""ORM model registry — single source of truth for expected database tables.

All ORM model modules are imported here to register their tables with
``Base.metadata``.  Use :func:`get_expected_tables` to discover the
canonical set of tables the application expects — both ``env.py`` (for
Alembic autogenerate) and ``anvil db verify`` (for schema integrity
checks) share this module instead of maintaining duplicate import lists.
"""

from __future__ import annotations

# Import all model modules to register them on Base.metadata.
# Each module defines a single ORM model with a ``__tablename__``.
from . import models  # noqa: F401  — registers models via models/__init__.py
from .models import external_model  # noqa: F401
from .models import model_import_job  # noqa: F401
from .base import Base


def get_expected_tables() -> frozenset[str]:
    """Return the canonical set of table names the application expects.

    All ORM models registered on ``Base.metadata`` are enumerated.
    Alembic-internal tables (``alembic_version``) are NOT included in
    metadata — they are created by Alembic itself.

    Returns
    -------
    frozenset[str]
        Table names that should exist in a healthy database.
    """
    return frozenset(Base.metadata.tables.keys())
