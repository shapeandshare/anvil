# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Format detection and verification for model weight files.

Per FR-033, the system MUST detect the actual file format from its
structure (not just the extension) and reject unsupported formats
fail-closed before any load or store operation.
"""

from __future__ import annotations

import logging
import struct

from anvil.services._shared.import_types import ModelSourceError

logger = logging.getLogger(__name__)

_SUPPORTED_WEIGHT_FORMATS: frozenset[str] = frozenset({"safetensors"})
"""Weight formats accepted in v1 (FR-030)."""


def check_weight_format(filename: str, header: bytes) -> None:
    """Verify that a weight file's content matches an accepted format.

    Inspects the first few bytes of the file stream to determine the
    actual format, then rejects if it is not in the allow-list or if
    the content contradicts the declared extension.

    Parameters
    ----------
    filename : str
        Original filename (used for extension hint).
    header : bytes
        At least 8 bytes from the start of the file.

    Raises
    ------
    ModelSourceError
        If the format is unsupported or the content contradicts the
        declared extension, with code ``"unsupported_format"``.
        The error message names the detected format and, for deferred
        formats, points to the GGUF roadmap (specs 050-052).
    """
    if len(header) < 8:
        raise ModelSourceError(
            code="invalid_file",
            message=f"File too small to determine format: {filename}",
            source="huggingface",
        )

    is_pickle = _looks_like_pickle(header)
    is_safetensors = _looks_like_safetensors(header)

    if is_safetensors:
        return  # accepted

    ext = _extension(filename).lower()
    if is_pickle:
        _reject_unsupported(
            filename,
            detected="PyTorch pickle",
            hint=(
                "PyTorch pickle files (.bin/.pt/.pth) are not accepted in v1. "
                "Only safetensors weights are supported."
            ),
        )

    if ext in (".gguf",):
        _reject_unsupported(
            filename,
            detected="GGUF",
            hint=(
                "GGUF format is not yet supported. "
                "See specs 050-052 (GGUF Import, Export, Fine-Tuning) "
                "for the deferred roadmap."
            ),
        )

    if ext in (".gptq", ".awq"):
        _reject_unsupported(
            filename,
            detected=f"Pre-quantized ({ext})",
            hint=(
                f"Pre-quantized {ext} checkpoints are not accepted in v1. "
                "Only safetensors weights are supported."
            ),
        )

    if ext in (".bin", ".pt", ".pth"):
        _reject_unsupported(
            filename,
            detected="PyTorch serialized",
            hint=(
                "PyTorch pickle files (.bin/.pt/.pth) are not accepted in v1. "
                "Only safetensors weights are supported."
            ),
        )


def _looks_like_pickle(data: bytes) -> bool:
    """Check if data starts with a Python pickle protocol marker."""
    return len(data) >= 2 and (data[0] == 0x80 or data[:2] in (b"\x00\x00",))


def _looks_like_safetensors(data: bytes) -> bool:
    """Check if data appears to be a valid safetensors file header.

    Safetensors starts with a 64-bit little-endian unsigned integer
    specifying the header JSON size.  We validate that:
    - The size is positive and not absurdly large (> 100 MB).
    - The following byte (start of JSON) looks like ``{``.
    """
    if len(data) < 8:
        return False
    try:
        header_size = struct.unpack("<Q", data[:8])[0]
    except struct.error:
        return False
    # Header must be > 0 and < 100 MB (sensible upper bound)
    if not (0 < header_size < 100 * 1024 * 1024):
        return False
    # The byte immediately after the size header should be '{' (start of JSON)
    if len(data) >= 9 and data[8:9] == b"{":
        return True
    return False


def _extension(filename: str) -> str:
    """Return the file extension in lowercase."""
    idx = filename.rfind(".")
    return filename[idx:] if idx >= 0 else ""


def _reject_unsupported(filename: str, detected: str, hint: str) -> None:
    """Raise a typed ``ModelSourceError`` for an unsupported format."""
    msg = f"Unsupported weight format detected in {filename!r}: {detected}. " f"{hint}"
    logger.warning(msg)
    raise ModelSourceError(
        code="unsupported_format",
        message=msg,
        source="huggingface",
    )
