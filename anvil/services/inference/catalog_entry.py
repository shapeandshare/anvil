# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""``CatalogEntry`` — a single entry in the curated model browser catalog."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .resource_envelope import ResourceEnvelope


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


__all__ = ["CatalogEntry"]
