# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""User-facing compute backend configuration enumeration."""

from enum import StrEnum


class ComputeBackend(StrEnum):
    """User-facing compute backend configuration identifiers.

    Attributes
    ----------
    AUTO : str
        Automatically select best available backend (``"auto"``).
    LOCAL_CPU : str
        Local CPU-only execution (``"local-cpu"``).
    LOCAL_GPU : str
        Local GPU-accelerated execution (``"local-gpu"``).
    MODAL : str
        Modal cloud GPU execution (``"modal"``).
    """

    AUTO = "auto"
    LOCAL_CPU = "local-cpu"
    LOCAL_GPU = "local-gpu"
    MODAL = "modal"
