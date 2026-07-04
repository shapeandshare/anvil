# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Lifecycle state enumeration for catalog entries."""

from __future__ import annotations

from enum import StrEnum


class LifecycleState(StrEnum):
    """Lifecycle state of a catalog entry.

    Attributes
    ----------
    ACTIVE : str
        Entry is visible in active listings (``"active"``).
    ARCHIVED : str
        Entry has been archived; hidden from default listings but
        referenced records still resolve (``"archived"``).
    """

    ACTIVE = "active"
    ARCHIVED = "archived"