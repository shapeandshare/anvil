"""Acceptance result value type.

Returned by :meth:`VersionedContentStore.accept_session` after a
successful ingestion session is folded into the canonical corpus.
"""

from __future__ import annotations

from pydantic import BaseModel


class AcceptResult(BaseModel):
    """Outcome of accepting a staged ingestion session.

    Parameters
    ----------
    version_id : int
        Internal version identifier for the new snapshot.
    manifest_digest : str
        SHA-256 hex digest of the manifest produced by this accept.
    version_number : int
        Monotonically increasing version number assigned to this
        snapshot.
    entry_count : int
        Number of entries folded into the corpus.
    total_bytes : int
        Total blob size in bytes across all accepted entries.
    """

    version_id: int
    manifest_digest: str
    version_number: int
    entry_count: int
    total_bytes: int
