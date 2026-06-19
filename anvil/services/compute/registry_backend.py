"""Internal registry backend name enumeration."""

from enum import StrEnum


class RegistryBackend(StrEnum):
    """Internal compute backend registry names.

    Attributes
    ----------
    LOCAL_STDLIB : str
        Local stdlib backend (``"local-stdlib"``).
    LOCAL_TORCH : str
        Local PyTorch backend (``"local-torch"``).
    MODAL : str
        Modal cloud GPU backend (``"modal"``).
    """

    LOCAL_STDLIB = "local-stdlib"
    LOCAL_TORCH = "local-torch"
    MODAL = "modal"