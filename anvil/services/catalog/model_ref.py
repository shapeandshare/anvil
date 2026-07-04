# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Model reference value object and catalog name derivation."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from .._shared.source_type import SourceType


class ModelRef(BaseModel):
    """Canonical reference to a model catalog entry.

    Attributes
    ----------
    name : str
        Catalog-registered model name. Characters restricted to
        ``[A-Za-z0-9._-]`` (URL-safe, MLflow-safe — no ``/`` or ``:``).
    version : int
        Model version number (>= 1).
    """

    model_config = {"frozen": True}

    name: str = Field(..., pattern=r"^[A-Za-z0-9._-]+$", min_length=1, max_length=255)
    version: int = Field(..., ge=1)

    def __str__(self) -> str:
        """Return the canonical ``"{name}/{version}"`` string form."""
        return f"{self.name}/{self.version}"


def derive_catalog_name(source_type: SourceType | str, identifier: str) -> str:
    """Derive a deterministic, URL-safe catalog name from a source
    type and identifier.

    Parameters
    ----------
    source_type : SourceType or str
        The source type (e.g. ``SourceType.HUGGINGFACE``).
    identifier : str
        Provider-specific model identifier (e.g.
        ``"TinyLlama/TinyLlama-1.1B-Chat-v1.0"``).

    Returns
    -------
    str
        Sanitized catalog name safe for use in the MLflow Model
        Registry and URLs.
    """
    if isinstance(source_type, str):
        source_type = SourceType(source_type)
    prefix = _SOURCE_PREFIXES[source_type]
    sanitized = _sanitize_for_catalog(identifier)
    return f"{prefix}--{sanitized}"


_SOURCE_PREFIXES: dict[str, str] = {
    "huggingface": "hf",
    "local": "local",
}
"""Mapping of source types to catalog name prefixes."""

_CATALOG_SAFE = re.compile(r"[^A-Za-z0-9._-]")


def _sanitize_for_catalog(name: str) -> str:
    """Replace characters unsafe for catalog names with ``-``.

    Parameters
    ----------
    name : str
        Raw identifier string.

    Returns
    -------
    str
        Identifier safe for use as a catalog name.
    """
    return _CATALOG_SAFE.sub("-", name)
