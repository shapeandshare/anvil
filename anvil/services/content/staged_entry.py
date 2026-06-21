"""Staged entry value type.

A ``StagedEntry`` represents a single blob that has been uploaded
(staged) during an ingestion session, before validation and acceptance.
"""

from __future__ import annotations

from pydantic import BaseModel


class StagedEntry(BaseModel):
    """A blob staged within an ingestion session.

    Parameters
    ----------
    path : str
        Relative path of the entry within the staging area.
    content_hash : str
        SHA-256 hex digest of the blob content.
    size_bytes : int
        Size of the blob in bytes.
    """

    path: str
    content_hash: str
    size_bytes: int
