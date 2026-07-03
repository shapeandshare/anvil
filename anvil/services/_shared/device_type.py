# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

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
        return {"cuda": "cuda:0", "mps": "mps", "cpu": "cpu"}[self.value]
