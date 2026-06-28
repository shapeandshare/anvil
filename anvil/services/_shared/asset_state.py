# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Asset state enumeration for external model download status."""

from __future__ import annotations

from enum import StrEnum


class AssetState(StrEnum):
    """Availability of a model's downloaded assets.

    Attributes
    ----------
    METADATA_ONLY : str
        No assets downloaded; only metadata exists (``"metadata_only"``).
    ASSETS_AVAILABLE : str
        Weights, tokenizer, and config have been downloaded (``"assets_available"``).
    ASSETS_PENDING : str
        Asset download is in progress (``"assets_pending"``).
    """

    METADATA_ONLY = "metadata_only"
    ASSETS_AVAILABLE = "assets_available"
    ASSETS_PENDING = "assets_pending"