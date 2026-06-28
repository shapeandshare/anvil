# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tokenizer load error — raised when a tokenizer cannot be loaded.

Covers missing files, corrupt files, parse failures, unknown families,
unsupported serializations, and vocabulary drift against a checkpoint.
"""

from __future__ import annotations


class TokenizerLoadError(Exception):
    """Raised when a tokenizer cannot be loaded or constructed.

    Parameters
    ----------
    message : str
        Human-readable error description.
    file_path : str or None
        Path to the problematic tokenizer artifact, if applicable.
    cause : str or None
        Root-cause description (e.g. ``"File not found"``,
        ``"JSON parse error at line 42"``), if available.

    Attributes
    ----------
    message : str
        Descriptive error message with file path and root cause.
    file_path : str or None
        Path to the problematic tokenizer file.
    cause : str or None
        Root-cause description.
    """

    def __init__(
        self,
        message: str,
        file_path: str | None = None,
        cause: str | None = None,
    ) -> None:
        self.file_path = file_path
        self.cause = cause
        parts = [message]
        if file_path:
            parts.append(f"file={file_path}")
        if cause:
            parts.append(f"cause={cause}")
        super().__init__("; ".join(parts))
