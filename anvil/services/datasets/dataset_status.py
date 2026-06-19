"""Dataset processing status enumeration."""

from enum import StrEnum


class DatasetStatus(StrEnum):
    """Lifecycle status of a dataset.

    Attributes
    ----------
    EMPTY : str
        Dataset created with no samples (``"empty"``).
    IMPORTING : str
        Dataset is actively importing samples (``"importing"``).
    READY : str
        Dataset has samples and is ready for training (``"ready"``).
    """

    EMPTY = "empty"
    IMPORTING = "importing"
    READY = "ready"