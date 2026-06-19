"""Training engine enumeration for compute backends."""

from enum import StrEnum


class TrainingEngine(StrEnum):
    """Training engine implementation options.

    Attributes
    ----------
    STDLIB : str
        Pure-Python stdlib training engine (``"stdlib"``).
    TORCH : str
        PyTorch-accelerated training engine (``"torch"``).
    """

    STDLIB = "stdlib"
    TORCH = "torch"