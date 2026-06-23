# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Registered model DTO for the model registry domain.

``RegisteredModel`` is a Pydantic ``BaseModel`` representing a model that
has been registered in the anvil model registry. It carries the model's
identity, human-readable name, version list, and creation timestamp.
"""

from __future__ import annotations

from pydantic import BaseModel


class RegisteredModel(BaseModel):
    """A model registered in the anvil model registry.

    Parameters
    ----------
    model_id : str
        Server-assigned unique identifier for this model.
    name : str
        Human-readable name for the registered model.
    versions : list[str]
        Ordered list of version identifiers for this model.
        Defaults to an empty list.
    created_at : str | None, optional
        ISO-8601 timestamp of when the model was registered.
        ``None`` when the timestamp is not available.
    """

    model_id: str
    name: str
    versions: list[str] = []
    created_at: str | None = None
