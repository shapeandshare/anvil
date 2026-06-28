# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tokenizer family enumeration for model metadata.

``TokenizerFamily`` records which tokenizer family a model uses,
driving inference/eval dispatch.
"""

from __future__ import annotations

from enum import StrEnum


class TokenizerFamily(StrEnum):
    """Tokenizer families supported by anvil.

    Attributes
    ----------
    CHAR : str
        Native character-level tokenizer (``Vocabulary`` / ``Tokenizer``).
    SUBWORD : str
        HuggingFace subword tokenizer (BPE / SentencePiece / Unigram).
    """

    CHAR = "char"
    SUBWORD = "subword"
