# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Dataset data transfer object.

``Dataset`` is a Pydantic ``BaseModel`` representing a dataset record as
returned by the anvil server API.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class Dataset(BaseModel):
    """A dataset record from the anvil server.

    Parameters
    ----------
    id : int
        Primary key.
    name : str
        Dataset name.
    description : str | None, optional
        Optional description.
    sample_count : int
        Number of samples in the dataset.
    created_at : datetime | None, optional
        Creation timestamp.
    updated_at : datetime | None, optional
        Last update timestamp.
    """

    id: int
    name: str
    description: str | None = None
    sample_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None
