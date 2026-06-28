# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""SentencePiece tokenizer wrapper.

Provides ``SentencePieceTokenizer`` (wrapping
``sentencepiece.SentencePieceProcessor``). Implements the ``Tokenizer``
protocol and is gated behind the ``[finetune]`` extra.
"""

from __future__ import annotations

from typing import Any

from ...core._tokenizer_base import Tokenizer

_HAS_SP_DEPS: bool = False
_HAS_SP_DEPS = False
try:
    import sentencepiece as _sentencepiece_lib

    _HAS_SP_DEPS = True
except ImportError:
    _sentencepiece_lib = None


class SentencePieceTokenizer(Tokenizer):
    """Tokenizer wrapper around ``sentencepiece.SentencePieceProcessor``.

    Wraps a SentencePiece processor loaded from a ``.model`` file.
    Requires the ``[finetune]`` extra.
    """

    def __init__(self, processor: Any) -> None:
        """Wrap a pre-loaded SentencePiece processor.

        Parameters
        ----------
        processor : sentencepiece.SentencePieceProcessor
            A loaded SentencePiece processor.
        """
        self._processor = processor

    @classmethod
    def from_file(cls, path: str) -> SentencePieceTokenizer:
        """Load a tokenizer from a ``.model`` file.

        Parameters
        ----------
        path : str
            Path to a SentencePiece ``.model`` file.

        Returns
        -------
        SentencePieceTokenizer
            A new wrapper instance.

        Raises
        ------
        ImportError
            If ``sentencepiece`` is not installed (the ``[finetune]``
            extra is missing).
        """
        if not _HAS_SP_DEPS:
            raise ImportError(
                "The sentencepiece library is required. "
                "Install with: pip install anvil[finetune]"
            )
        processor = _sentencepiece_lib.SentencePieceProcessor()
        processor.load(path)
        return cls(processor)

    def encode(self, text: str) -> list[int]:
        """Encode text into token IDs.

        Parameters
        ----------
        text : str
            Input text.

        Returns
        -------
        list of int
            Token ID sequence.
        """
        return list(self._processor.encode(text))

    def decode(self, ids: list[int]) -> str:
        """Decode token IDs back into text.

        Parameters
        ----------
        ids : list of int
            Token ID sequence.

        Returns
        -------
        str
            Decoded text.
        """
        return str(self._processor.decode(ids))

    @property
    def vocab_size(self) -> int:
        """Total vocabulary size."""
        return int(self._processor.get_piece_size())

    @property
    def bos_id(self) -> None:
        """SentencePiece tokenizers do not expose a single BOS ID.

        Returns
        -------
        None
        """
        return None
