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