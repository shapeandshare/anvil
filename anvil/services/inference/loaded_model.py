# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Loaded model container — holds a ``LlamaModel`` with its tokenizer and metadata.

Provides the ``LoadedModel`` class for encapsulating a trained model
together with its tokenizer and registry metadata.  Optionally carries
a reference to a LoRA adapter artifact path.
"""

from typing import Any

from ...core._tokenizer_base import Tokenizer
from ...core.engine import LlamaModel


class LoadedModel:
    """Container for a loaded LlamaModel with its tokenizer and metadata."""

    def __init__(
        self,
        model: LlamaModel,
        tokenizer: Tokenizer,
        model_id: int | None,
        version: int | None,
        name: str,
        is_demo: bool = False,
        adapter_path: str | None = None,
    ):
        self.model = model
        self.tokenizer = tokenizer
        self.model_id = model_id
        self.version = version
        self.name = name
        self.is_demo = is_demo
        self.adapter_path = adapter_path

    @property
    def chars(self) -> list[str]:
        """Character vocabulary for display labels.

        Char-level tokenizers expose a ``chars`` attribute; subword
        tokenizers return an empty list.
        """
        return getattr(self.tokenizer, "chars", [])

    @property
    def bos_id(self) -> int | None:
        """BOS token ID, delegating to the attached tokenizer."""
        return self.tokenizer.bos_id

    def info(self) -> dict[str, Any]:
        """Return model metadata as a dictionary.

        Returns
        -------
        dict[str, Any]
            Dict with keys ``id``, ``version``, ``name``, ``is_demo``,
            and ``tokenizer`` (family, serialization_type, vocab_size).
        """
        base: dict[str, Any] = {
            "id": self.model_id,
            "version": self.version,
            "name": self.name,
            "is_demo": self.is_demo,
        }
        # Surface tokenizer metadata for the API response
        if hasattr(self.model, "tokenizer_family"):
            base["tokenizer"] = {
                "family": self.model.tokenizer_family,
                "serialization_type": self.model.serialization_type,
                "vocab_size": self.tokenizer.vocab_size,
            }
        return base
