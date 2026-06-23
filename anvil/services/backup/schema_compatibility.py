# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Schema-compatibility check results for restore."""

from enum import StrEnum


class SchemaCompatibility(StrEnum):
    """Result of comparing a backup manifest's schema revision against the
    running deployment's Alembic head.

    ``OK`` — same head, fully compatible.
    ``WARN`` — same head with minor version drift, allowed with warning.
    ``BLOCKED`` — different Alembic head; restore is refused.
    """

    OK = "ok"
    WARN = "warn"
    BLOCKED = "blocked"
