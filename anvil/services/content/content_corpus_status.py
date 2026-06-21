# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Corpus lifecycle status enumeration."""

from enum import StrEnum


class ContentCorpusStatus(StrEnum):
    """Lifecycle status of a versioned content corpus.

    Attributes
    ----------
    DRAFT : str
        Corpus is being prepared; not yet active (``"draft"``).
    ACTIVE : str
        Corpus is live and accepting content (``"active"``).
    ARCHIVED : str
        Corpus is frozen for further changes (``"archived"``).
    """

    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"
