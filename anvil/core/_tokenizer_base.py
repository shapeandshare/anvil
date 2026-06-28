# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Abstract tokenizer protocol — zero-dependency interface for all tokenizers.

Defines the ``Tokenizer`` abstract base class that both the native
character-level vocabulary and HuggingFace subword tokenizers implement.
This module lives in ``anvil/core/`` and has ZERO third-party dependencies
(Article I).
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class Tokenizer(ABC):
    """Abstract tokenizer — all tokenizer implementations must satisfy this protocol.

    Every method and property is abstract. Implementations must provide
    all of them.
    """

    @abstractmethod
    def encode(self, text: str) -> list[int]:
        """Encode text into a sequence of token IDs.

        Parameters
        ----------
        text : str
            Input text to tokenize.

        Returns
        -------
        list of int
            Token ID sequence.
        """

    @abstractmethod
    def decode(self, ids: list[int]) -> str:
        """Decode a sequence of token IDs back into text.

        Parameters
        ----------
        ids : list of int
            Token ID sequence to decode.

        Returns
        -------
        str
            The reconstructed text.
        """

    @property
    @abstractmethod
    def vocab_size(self) -> int:
        """Total vocabulary size, including any special/added tokens.

        Returns
        -------
        int
            Number of tokens in the vocabulary.
        """

    @property
    @abstractmethod
    def bos_id(self) -> int | None:
        """BOS (beginning-of-sequence) token ID.

        Char-level tokenizers return their BOS index (``len(chars)``).
        Subword tokenizers return ``None`` since BOS is a named special
        token handled internally by :meth:`decode`.

        Returns
        -------
        int or None
            The BOS token ID, or ``None`` if the concept does not
            apply to this tokenizer family.
        """
