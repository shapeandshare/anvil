# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Pydantic models for the HuggingFace Model Browser.

``ResourceEnvelope``, ``CatalogEntry``, and ``CuratedCatalog`` define
the shape of curated model metadata consumed by the model-browser UI
and HF API integration layer.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ResourceEnvelope(BaseModel):
    """Hardware resource requirements for a curated model entry.

    Attributes
    ----------
    min_ram_gb : float
        Minimum system RAM in GB. Must be non-negative.
    min_vram_per_backend : dict[str, float]
        Per-backend minimum VRAM in GB. Must include at least a
        ``"cpu"`` key.
    supported_methods : list[str]
        Supported fine-tuning methods. Must contain at least one entry.
    """

    min_ram_gb: float = Field(ge=0, description="Minimum system RAM in GB")
    min_vram_per_backend: dict[str, float] = Field(
        description="Per-backend minimum VRAM in GB"
    )
    supported_methods: list[str] = Field(
        min_length=1, description="Supported fine-tuning methods"
    )

    @field_validator("min_vram_per_backend")
    @classmethod
    def _ensure_cpu_key(cls, v: dict[str, float]) -> dict[str, float]:
        """Validate that the VRAM dict contains a ``"cpu"`` key.

        Parameters
        ----------
        v : dict[str, float]
            The per-backend VRAM mapping to validate.

        Returns
        -------
        dict[str, float]
            The validated mapping unchanged.

        Raises
        ------
        ValueError
            If the ``"cpu"`` key is missing from the dictionary.
        """
        if "cpu" not in v:
            msg = "min_vram_per_backend must include a 'cpu' key"
            raise ValueError(msg)
        return v


class CatalogEntry(BaseModel):
    """A single entry in the curated model browser catalog.

    Attributes
    ----------
    hf_id : str
        Stable HuggingFace model identifier (e.g.
        ``"shapeandshare/tiny-magic-1b"``).
    display_name : str
        Human-readable model name.
    params : str
        Parameter count label (e.g. ``"1.1B"``, ``"7B"``).
    license : str
        SPDX license identifier (e.g. ``"MIT"``, ``"apache-2.0"``).
    architecture : str
        HuggingFace architecture class (e.g. ``"LlamaForCausalLM"``).
    tokenizer_family : str
        Tokenizer family identifier (e.g. ``"sentencepiece"``,
        ``"tokenizers"``).
    url : str
        HuggingFace model page URL.
    tags : list[str]
        Free-form tags for filtering and organisation. Defaults to
        empty list.
    resource_envelope : ResourceEnvelope
        Hardware resource requirements for this model.
    """

    hf_id: str
    display_name: str
    params: str
    license: str
    architecture: str
    tokenizer_family: str
    url: str
    tags: list[str] = Field(default_factory=list)
    resource_envelope: ResourceEnvelope


class CuratedCatalog(BaseModel):
    """Collection of curated model entries for the browser.

    Attributes
    ----------
    catalog : list[CatalogEntry]
        Ordered list of curated model entries.
    """

    catalog: list[CatalogEntry]


__all__ = [
    "CatalogEntry",
    "CuratedCatalog",
    "ResourceEnvelope",
]
