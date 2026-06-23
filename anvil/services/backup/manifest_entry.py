# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Per-file entry in a backup manifest."""

from pydantic import BaseModel


class ManifestEntry(BaseModel):
    """A single file tracked in the backup manifest.

    Parameters
    ----------
    path : str
        Path relative to the archive root.
    sha256 : str
        Hex-encoded SHA-256 digest of the uncompressed file.
    size : int
        Uncompressed size in bytes.
    """

    path: str
    sha256: str
    size: int
