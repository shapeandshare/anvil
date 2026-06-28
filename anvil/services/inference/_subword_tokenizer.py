# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""HuggingFace subword tokenizer wrappers.

Provides ``HFFastTokenizer`` (wrapping ``tokenizers.Tokenizer``).
Implements the ``Tokenizer`` protocol and is gated behind the
``[finetune]`` extra — they MUST NOT be importable in a base install.
"""

from __future__ import annotations

from typing import Any

from ...core._tokenizer_base import Tokenizer

_HAS_FINETUNE_DEPS: bool = False
