# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

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
