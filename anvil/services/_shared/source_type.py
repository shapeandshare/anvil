# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Source type enumeration for external model imports."""

from __future__ import annotations

from enum import StrEnum


class SourceType(StrEnum):
    """Origin source of an external model.

    Attributes
    ----------
    HUGGINGFACE : str
        HuggingFace Hub repository (``"huggingface"``).
    LOCAL : str
        Local file or directory path (``"local"``).
    """

    HUGGINGFACE = "huggingface"
    LOCAL = "local"
