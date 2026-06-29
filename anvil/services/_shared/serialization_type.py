# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Serialization type enumeration for tokenizer artifacts.

``SerializationType`` records how a model's tokenizer artifact is
serialised on disk, enabling the correct loader to be selected.
"""

from __future__ import annotations

from enum import StrEnum


class SerializationType(StrEnum):
    """Supported tokenizer serialization formats.

    Attributes
    ----------
    CHAR_JSON : str
        anvil's native character-level tokenizer JSON format.
    HF_FAST : str
        HuggingFace fast tokenizer (``tokenizer.json``, self-contained).
    SENTENCEPIECE : str
        SentencePiece binary model file (``tokenizer.model`` /
        ``sentencepiece.model``), used by Llama 1/2 and Gemma.
    """

    CHAR_JSON = "char_json"
    HF_FAST = "hf_fast"
    SENTENCEPIECE = "sentencepiece"
