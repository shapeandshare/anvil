# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""TokenizerFactory — resolves a ``Tokenizer`` from model metadata."""
# pylint: disable=import-outside-toplevel

from __future__ import annotations

import logging
from pathlib import Path

from ...core._tokenizer_base import Tokenizer
from ...core.vocabulary import Vocabulary
from .._shared.serialization_type import SerializationType
from .._shared.tokenizer_family import TokenizerFamily
from .._shared.tokenizer_load_error import TokenizerLoadError

logger = logging.getLogger("anvil.services.inference.tokenizer")


def create_tokenizer(
    *,
    tokenizer_family: str,
    serialization_type: str,
    chars: list[str] | None = None,
    artifact_dir: str | Path | None = None,
) -> Tokenizer:
    """Create a ``Tokenizer`` from model metadata.

    Parameters
    ----------
    tokenizer_family : str
        The tokenizer family (``"char"`` or ``"subword"``).
    serialization_type : str
        The serialization format (``"char_json"``, ``"hf_fast"``,
        or ``"sentencepiece"``).
    chars : list of str or None
        Character list for char-level tokenizers. Required when
        ``serialization_type`` is ``"char_json"``.
    artifact_dir : str or Path or None
        Directory containing tokenizer artifact files. Required when
        ``serialization_type`` is ``"hf_fast"`` or ``"sentencepiece"``.

    Returns
    -------
    Tokenizer
        A tokenizer instance matching the requested type.

    Raises
    ------
    TokenizerLoadError
        If the tokenizer cannot be loaded (unknown family, unsupported
        serialization, missing or corrupt artifact file).
    """
    logger.info(
        "Creating tokenizer: family=%s, serialization=%s",
        tokenizer_family,
        serialization_type,
    )

    try:
        TokenizerFamily(tokenizer_family)  # validate (raises ValueError)
    except ValueError:
        valid = ", ".join(m.value for m in TokenizerFamily)
        raise TokenizerLoadError(  # noqa: B904
            f"Unknown tokenizer family: {tokenizer_family}",
            cause=f"Expected one of: {valid}",
        )

    try:
        ser_type = SerializationType(serialization_type)
    except ValueError:
        valid = ", ".join(m.value for m in SerializationType)
        raise TokenizerLoadError(  # noqa: B904
            f"Unsupported serialization type: {serialization_type}",
            cause=f"Expected one of: {valid}",
        )

    if ser_type == SerializationType.CHAR_JSON:
        if chars is None:
            raise TokenizerLoadError(
                "char_json tokenizer requires a character list",
                cause="chars was None",
            )
        return Vocabulary.from_chars(chars)

    if artifact_dir is None:
        raise TokenizerLoadError(
            f"Subword tokenizer ({ser_type}) requires an artifact directory",
        )

    artifact_path = Path(artifact_dir)

    if ser_type == SerializationType.HF_FAST:
        tokenizer_path = artifact_path / "tokenizer.json"
        if not tokenizer_path.exists():
            raise TokenizerLoadError(
                f"HuggingFace fast tokenizer file not found: {tokenizer_path}",
                file_path=str(tokenizer_path),
                cause="File not found",
            )
        try:
            from ._subword_tokenizer import HFFastTokenizer

            return HFFastTokenizer.from_file(str(tokenizer_path))
        except ImportError:
            raise TokenizerLoadError(  # noqa: B904
                "HuggingFace fast tokenizer requires the [finetune] extra",
                cause="Run: pip install anvil[finetune]",
            )
        except Exception as exc:
            raise TokenizerLoadError(  # noqa: B904
                f"Failed to load HF fast tokenizer from {tokenizer_path}",
                file_path=str(tokenizer_path),
                cause=str(exc),
            )

    if ser_type == SerializationType.SENTENCEPIECE:
        # Try common SentencePiece model file names
        sp_paths = [
            artifact_path / "tokenizer.model",
            artifact_path / "sentencepiece.model",
        ]
        sp_file: Path | None = None
        for p in sp_paths:
            if p.exists():
                sp_file = p
                break
        if sp_file is None:
            raise TokenizerLoadError(
                f"SentencePiece model file not found in {artifact_dir}. "
                f"Searched: {[str(p) for p in sp_paths]}",
                file_path=str(artifact_dir),
                cause="No .model file found",
            )
        try:
            from ._subword_tokenizer import SentencePieceTokenizer

            return SentencePieceTokenizer.from_file(str(sp_file))
        except ImportError:
            raise TokenizerLoadError(  # noqa: B904
                "SentencePiece tokenizer requires the [finetune] extra",
                cause="Run: pip install anvil[finetune]",
            )
        except Exception as exc:
            raise TokenizerLoadError(  # noqa: B904
                f"Failed to load SentencePiece tokenizer from {sp_file}",
                file_path=str(sp_file),
                cause=str(exc),
            )

    # Unreachable if SerializationType is exhaustive, but satisfy the type checker
    raise TokenizerLoadError(
        f"Unhandled serialization type: {serialization_type}",
    )
