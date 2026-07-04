# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Catalog kind enumeration for model entries."""

from __future__ import annotations

from enum import StrEnum


class CatalogKind(StrEnum):
    """Type of a model catalog entry.

    Values
    ------
    TRAINED : str
        Model trained within anvil (``"trained"``).
    EXTERNAL : str
        Model imported from an external source (``"external"``).
    MERGED : str
        Model produced by merging a LoRA adapter into a base
        (``"merged"``).
    ADAPTER : str
        LoRA adapter promoted to a catalog entry. Reserved for
        Spec 065; not emitted in this feature (``"adapter"``).
    """

    TRAINED = "trained"
    EXTERNAL = "external"
    MERGED = "merged"
    ADAPTER = "adapter"
