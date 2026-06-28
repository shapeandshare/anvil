# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""ModelSource protocol and supporting imports for model-import.

Defines the ``ModelSource`` structural protocol (PEP 544) that all
external-model resolvers implement, consistent with the
``ComputeBackendProtocol`` pattern in ``anvil/services/compute/``.
"""

from __future__ import annotations

from typing import Protocol

from .._shared.import_types import ModelMetadata


class ModelSource(Protocol):
    """Structural protocol for resolving external model metadata.

    Any class with a ``name`` attribute and an
    ``async def resolve_metadata`` method satisfying this signature
    is a valid ``ModelSource`` — no explicit registration or
    subclassing required (PEP 544 structural typing).

    Attributes
    ----------
    name : str
        Human-readable source identifier.
    """

    name: str

    async def resolve_metadata(
        self,
        identifier: str,
        *,
        revision: str = "main",
        token: str | None = None,
    ) -> ModelMetadata:
        """Resolve model metadata from the source.

        Parameters
        ----------
        identifier : str
            Source-specific model identifier (HF repo ID or local path).
        revision : str
            Source revision, branch, or commit SHA. Defaults to ``"main"``.
        token : str | None
            Optional authentication token (e.g. ``HF_TOKEN`` for HF Hub).

        Returns
        -------
        ModelMetadata
            Resolved metadata fields from the source.

        Raises
        ------
        ModelSourceError
            On resolution failure with a typed error code.
        """
        ...  # pragma: no cover
