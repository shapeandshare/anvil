# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Result of an on-demand backup integrity verification."""

from pydantic import BaseModel


class VerifyResult(BaseModel):
    """Outcome of a ``verify`` operation (FR-025).

    Parameters
    ----------
    backup_id : str
    valid : bool
        ``True`` when every file's SHA-256 matches the manifest.
    checked_count : int
        Number of files verified.
    mismatched : list[str]
        Paths whose checksum did not match; empty when ``valid``.
    """

    backup_id: str
    valid: bool = True
    checked_count: int = 0
    mismatched: list[str] = []
