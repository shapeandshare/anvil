# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Reconstructable vocabulary from a character list.

Provides a ``Vocabulary`` class that mirrors ``Tokenizer`` encode/decode
semantics (BOS-wrapped) but can be constructed directly from a sorted
character list instead of requiring the original documents. This is
useful when loading a pre-trained model whose character mapping is
known.
"""

from __future__ import annotations

from ._tokenizer_base import Tokenizer


class Vocabulary(Tokenizer):
    """Reconstructable character vocabulary with BOS-wrapped encoding.

    Matches ``Tokenizer`` encode/decode semantics exactly (BOS-wrapped),
    but is constructed from a pre-sorted character list rather than raw
    documents. This makes it suitable for reconstructing the vocabulary
    of a saved model.

    The BOS token ID is always ``len(chars)`` and the vocabulary size
    is ``len(chars) + 1``.
    """

    def __init__(self, chars: list[str]):
        """Initialize the vocabulary from a sorted character list.

        Parameters
        ----------
        chars : list of str
            Sorted list of unique characters that make up the
            vocabulary. The order determines the token IDs.
        """
        self.chars = chars
        self._bos_id = len(chars)
        self._vocab_size = len(chars) + 1
        self._char_to_id = {ch: i for i, ch in enumerate(chars)}

    @property
    def bos_id(self) -> int | None:
        """BOS token ID for this vocabulary.

        Returns
        -------
        int
            The BOS token index (``len(chars)``).
        """
        return self._bos_id

    @property
    def vocab_size(self) -> int:
        """Vocabulary size including the BOS token.

        Returns
        -------
        int
            ``len(chars) + 1``.
        """
        return self._vocab_size

    @classmethod
    def from_chars(cls, chars: list[str]) -> Vocabulary:
        """Create a ``Vocabulary`` from a character list.

        This is an alias for the constructor, provided for API
        consistency.

        Parameters
        ----------
        chars : list of str
            Sorted list of unique characters.

        Returns
        -------
        Vocabulary
            A new vocabulary instance.
        """
        return cls(chars)

    def encode(self, text: str) -> list[int]:
        """Encode a string into BOS-wrapped token IDs.

        Characters not in the vocabulary are silently skipped. The
        output is wrapped with BOS markers on both ends.

        Parameters
        ----------
        text : str
            Input string to encode.

        Returns
        -------
        list of int
            Token IDs with leading and trailing BOS tokens.
        """
        return (
            [self._bos_id]
            + [self._char_to_id[ch] for ch in text if ch in self._char_to_id]
            + [self._bos_id]
        )

    def decode(self, ids: list[int]) -> str:
        """Decode token IDs back into a string.

        BOS tokens are silently omitted from the output. Out-of-range
        IDs are skipped.

        Parameters
        ----------
        ids : list of int
            Token ID sequence to decode.

        Returns
        -------
        str
            The reconstructed string.
        """
        return "".join(
            self.chars[i] for i in ids if i != self.bos_id and 0 <= i < len(self.chars)
        )
