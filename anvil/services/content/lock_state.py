"""Advisory checkout lock state enumeration."""

from enum import StrEnum


class LockState(StrEnum):
    """State of an advisory checkout lock.

    Attributes
    ----------
    HELD : str
        Lock is actively held (``"held"``).
    RELEASED : str
        Lock has been released (``"released"``).
    """

    HELD = "held"
    RELEASED = "released"