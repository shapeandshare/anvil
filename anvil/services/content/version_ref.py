"""Version reference value type.

A ``VersionRef`` uniquely identifies a fixed version of a corpus manifest
within the content repository. It captures both the human-readable version
number and the content-addressed digest for integrity verification.
"""

from __future__ import annotations

from pydantic import BaseModel


class VersionRef(BaseModel):
    """Pointer to a specific manifest version in a corpus.

    Parameters
    ----------
    manifest_digest : str
        SHA-256 hex digest of the canonical manifest JSON.
    version_id : int
        Internal auto-increment version identifier.
    version_number : int
        Monotonically increasing version number within the corpus.
    label : str | None
        Optional human-readable label (e.g. ``"v2-tuned"``).
    """

    manifest_digest: str
    version_id: int
    version_number: int
    label: str | None = None
