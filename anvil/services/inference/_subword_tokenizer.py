# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""HuggingFace fast tokenizer wrapper.

Provides ``HFFastTokenizer`` (wrapping ``tokenizers.Tokenizer``).
Implements the ``Tokenizer`` protocol and is gated behind the
``[finetune]`` extra.
"""

from __future__ import annotations

from typing import Any

from ...core._tokenizer_base import Tokenizer

_HAS_FINETUNE_DEPS: bool = False
try:
    import tokenizers as _tokenizers_lib

    _HAS_FINETUNE_DEPS = True
except ImportError:
    _tokenizers_lib = None


class HFFastTokenizer(Tokenizer):
    """Tokenizer wrapper around HuggingFace ``tokenizers.Tokenizer``.

    Wraps a ``tokenizers.Tokenizer`` loaded from a ``tokenizer.json``
    file. Requires the ``[finetune]`` extra.
    """

    def __init__(self, tokenizer: Any) -> None:
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
        hf_tokenizer = _tokenizers_lib.Tokenizer.from_file(path)
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
        encoding = self._tokenizer.encode(text)
        return list(encoding.ids)

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
        return str(self._tokenizer.decode(ids, skip_special_tokens=True))

    @property
    def vocab_size(self) -> int:
        """Total vocabulary size including added tokens."""
        return int(self._tokenizer.get_vocab_size(with_added_tokens=True))

    @property
    def bos_id(self) -> None:
        """Subword tokenizers do not expose a single BOS ID.

        Returns
        -------
        None
        """
        return None
