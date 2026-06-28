# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""HuggingFace subword tokenizer wrappers.

Provides ``HFFastTokenizer`` (wrapping ``tokenizers.Tokenizer``) and
``SentencePieceTokenizer`` (wrapping ``sentencepiece.SentencePieceProcessor``).
Both implement the ``Tokenizer`` protocol and are gated behind the
``[finetune]`` extra — they MUST NOT be importable in a base install.
"""

from __future__ import annotations

from ...core._tokenizer_base import Tokenizer

_HAS_FINETUNE_DEPS = False
try:
    from tokenizers import Encoding as _Encoding
    from tokenizers import Tokenizer as _HFTokenizer

    _HAS_FINETUNE_DEPS = True
except ImportError:
    _HFTokenizer = None  # type: ignore[assignment]
    _Encoding = None  # type: ignore[assignment]


class HFFastTokenizer(Tokenizer):
    """Tokenizer wrapper around HuggingFace ``tokenizers.Tokenizer``.

    Wraps a ``tokenizers.Tokenizer`` loaded from a ``tokenizer.json``
    file. Requires the ``[finetune]`` extra.
    """

    def __init__(self, tokenizer: _HFTokenizer) -> None:  # type: ignore[arg-type]
        """Wrap a pre-loaded HF tokenizer instance.

        Parameters
        ----------
        tokenizer : tokenizers.Tokenizer
            A loaded fast tokenizer.
        """
        self._tokenizer = tokenizer

    @classmethod
    def from_file(cls, path: str) -> HFFastTokenizer:
        """Load a tokenizer from a ``tokenizer.json`` file.

        Parameters
        ----------
        path : str
            Path to a ``tokenizer.json`` file.

        Returns
        -------
        HFFastTokenizer
            A new wrapper instance.

        Raises
        ------
        ImportError
            If ``tokenizers`` is not installed (the ``[finetune]`` extra
            is missing).
        """
        if not _HAS_FINETUNE_DEPS:
            raise ImportError(
                "The HuggingFace tokenizers library is required. "
                "Install with: pip install anvil[finetune]"
            )
        hf_tokenizer = _HFTokenizer.from_file(path)
        return cls(hf_tokenizer)

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
        encoding: _Encoding = self._tokenizer.encode(text)
        return encoding.ids

    def decode(self, ids: list[int]) -> str:
        """Decode token IDs back into text.

        Parameters
        ----------
        ids : list of int
            Token ID sequence.

        Returns
        -------
        str
            Decoded text, with special tokens stripped.
        """
        return self._tokenizer.decode(ids, skip_special_tokens=True)

    @property
    def vocab_size(self) -> int:
        """Total vocabulary size including added tokens."""
        return self._tokenizer.get_vocab_size(with_added_tokens=True)

    @property
    def bos_id(self) -> None:
        """Subword tokenizers do not expose a single BOS ID.

        Returns
        -------
        None
        """
        return None


_HAS_SP_DEPS = False
try:
    import sentencepiece as _sentencepiece

    _HAS_SP_DEPS = True
except ImportError:
    pass


class SentencePieceTokenizer(Tokenizer):
    """Tokenizer wrapper around ``sentencepiece.SentencePieceProcessor``.

    Wraps a SentencePiece processor loaded from a ``.model`` file.
    Requires the ``[finetune]`` extra.
    """

    def __init__(self, processor: _sentencepiece.SentencePieceProcessor) -> None:  # type: ignore[name-defined]
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
        processor = _sentencepiece.SentencePieceProcessor()
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
        return self._processor.encode(text)

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
        return self._processor.decode(ids)

    @property
    def vocab_size(self) -> int:
        """Total vocabulary size."""
        return self._processor.get_piece_size()

    @property
    def bos_id(self) -> None:
        """SentencePiece tokenizers do not expose a single BOS ID.

        Returns
        -------
        None
        """
        return None
