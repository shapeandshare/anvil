# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Schema version — bumped when migrations are squashed.

``SCHEMA_VERSION`` is an integer that MUST be bumped in the same commit
that rewrites/squashes Alembic migration files.  At startup the
application reads ``PRAGMA user_version`` from the SQLite database and
refuses to start if it is non-zero and does not match this constant.
"""

SCHEMA_VERSION: int = 1
"""Expected database schema version.

Bump this integer whenever Alembic migrations are squashed (i.e., an
existing migration file is rewritten to create a different set of
tables).  Databases created before the squash will have a stale
*user_version* and will be rejected at startup.
"""
