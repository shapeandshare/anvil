"""Device type enumeration for compute backends.

``DeviceType`` enumerates the available compute device backends
for PyTorch or stdlib training.
"""

from enum import StrEnum


class DeviceType(StrEnum):
    """Available compute device types.

    Attributes
    ----------
    CPU : str
        Central processing unit (``"cpu"``).
    CUDA : str
        NVIDIA GPU via CUDA (``"cuda"``).
    MPS : str
        Apple Silicon GPU via Metal Performance Shaders (``"mps"``).
    """

    CPU = "cpu"
    CUDA = "cuda"
    MPS = "mps"

    def to_torch_device(self) -> str:
        """Return a torch-compatible device string for this type.

        Returns
        -------
        str
            ``"cuda:0"`` for CUDA, ``"mps"`` for MPS, ``"cpu"`` for CPU.
        """
        return {"cuda": "cuda:0", "mps": "mps", "cpu": "cpu"}[self.value]