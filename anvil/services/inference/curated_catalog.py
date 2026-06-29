# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""``CuratedCatalog`` — collection of curated model entries for the browser."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .catalog_entry import CatalogEntry


class CuratedCatalog(BaseModel):
    """Collection of curated model entries for the browser.

    Attributes
    ----------
    catalog : list[CatalogEntry]
        Ordered list of curated model entries.
    """

    catalog: list[CatalogEntry] = Field(description="List of curated model entries")


__all__ = ["CuratedCatalog"]
