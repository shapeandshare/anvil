"""Adapter wrapping ``transformers.PreTrainedTokenizer`` to satisfy the ``Tokenizer`` interface.

Used when composing adapters for HuggingFace subword models whose tokenizer
does not map directly to the anvil built-in formats. Requires the ``[finetune]``
extra.
"""

from __future__ import annotations

from typing import Any

from ...core._tokenizer_base import Tokenizer


class TransformersTokenizerAdapter(Tokenizer):
    """Wrap a ``transformers.PreTrainedTokenizer`` to satisfy the ``Tokenizer`` interface.

    Parameters
    ----------
    tokenizer : transformers.PreTrainedTokenizer
        A loaded HF tokenizer instance.
    """

    def __init__(self, tokenizer: Any) -> None:
        self._tokenizer = tokenizer

    def encode(self, text: str) -> list[int]:
        """Encode text using the HF tokenizer.

        Parameters
        ----------
        text : str
            Input text.

        Returns
        -------
        list of int
            Token ID sequence.
        """
        return self._tokenizer.encode(text)  # type: ignore[no-any-return]

    def decode(self, ids: list[int]) -> str:
        """Decode token IDs using the HF tokenizer.

        Parameters
        ----------
        ids : list of int
            Token ID sequence.

        Returns
        -------
        str
            Decoded text with special tokens stripped.
        """
        return str(self._tokenizer.decode(ids, skip_special_tokens=True))

    @property
    def vocab_size(self) -> int:
        """Total vocabulary size."""
        return int(self._tokenizer.vocab_size)

    @property
    def bos_id(self) -> int | None:
        """BOS token ID from the HF tokenizer."""
        val: int | None = self._tokenizer.bos_token_id
        return val
