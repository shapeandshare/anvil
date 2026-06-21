"""Ingestion session reference value type.

An ``IngestSessionRef`` identifies an active ingestion session within a
corpus. Sessions provide isolated staging areas where content can be
staged, validated, and then either accepted or abandoned atomically.
"""

from __future__ import annotations

from pydantic import BaseModel


class IngestSessionRef(BaseModel):
    """Reference to an active ingestion session.

    Parameters
    ----------
    session_id : int
        Internal auto-increment session identifier.
    corpus_id : int
        Internal identifier of the target corpus.
    staging_key : str
        Opaque key identifying the staging area for this session.
    status : str
        Current session status. One of ``"open"``, ``"validating"``,
        ``"accepted"``, or ``"failed"`` (see ``IngestStatus`` enum).
    """

    session_id: int
    corpus_id: int
    staging_key: str
    status: str