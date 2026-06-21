# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Loaded model container — holds a ``LlamaModel`` with its vocabulary and metadata.

Provides the ``LoadedModel`` class for encapsulating a trained model
together with its character vocabulary and registry metadata.
"""

from typing import Any

from ...core.engine import LlamaModel
from ...core.vocabulary import Vocabulary


class LoadedModel:
    """Container for a loaded LlamaModel with its vocabulary and metadata."""

    def __init__(
        self,
        model: LlamaModel,
        chars: list[str],
        model_id: int | None,
        version: int | None,
        name: str,
        is_demo: bool = False,
    ):
        self.model = model
        self.chars = chars
        self.vocab = Vocabulary.from_chars(chars)
        self.model_id = model_id
        self.version = version
        self.name = name
        self.is_demo = is_demo

    def info(self) -> dict[str, Any]:
        """Return model metadata as a dictionary.

        Returns
        -------
        dict[str, Any]
            Dict with keys ``id``, ``version``, ``name``, and
            ``is_demo``.
        """
        return {
            "id": self.model_id,
            "version": self.version,
            "name": self.name,
            "is_demo": self.is_demo,
        }
