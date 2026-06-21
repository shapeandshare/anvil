"""Garbage collection and retention service for the versioned content
repository.

``RetentionService`` provides a single ``collect_garbage()`` entry
point that removes unreferenced content blobs (both DB metadata and
on-disk files) and cleans up abandoned ingestion sessions older than
30 days.

Protected versions
    A version is considered *retention-protected* if it has at least
    one :class:`VersionRunRef` (linked by an MLflow training run) or
    has a :class:`ContentTag` with ``gc_protected=True``.  Blobs
    referenced by protected versions are never removed.
"""

from __future__ import annotations

import asyncio
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.models.content_tag import ContentTag
from ...db.models.content_version_run_ref import VersionRunRef
from ...db.repositories.content_blobs import ContentBlobRepository
from ...db.repositories.content_corpora import ContentCorpusRepository
from ...db.repositories.content_ingest_sessions import ContentIngestSessionRepository
from ...db.repositories.content_versions import ContentVersionRepository
from .ingest_status import IngestStatus


class RetentionService:
    """Garbage collection for the versioned content repository.

    Removes unreferenced blobs (DB rows and on-disk files) and cleans
    up abandoned or failed ingestion sessions that have exceeded the
    30-day retention window.

    Parameters
    ----------
    corpus_repo : ContentCorpusRepository
        Repository for ``ContentCorpus`` entities.
    version_repo : ContentVersionRepository
        Repository for ``ContentVersion`` and ``ContentEntry``
        entities.
    blob_repo : ContentBlobRepository
        Repository for ``ContentBlob`` metadata.
    session_repo : ContentIngestSessionRepository
        Repository for ``IngestSession`` entities.
    db_session : AsyncSession
        SQLAlchemy async session for direct queries on tag and
        run-ref models.
    content_dir : str
        Root directory of the content store (parent of ``blobs/``).
    """

    def __init__(
        self,
        corpus_repo: ContentCorpusRepository,
        version_repo: ContentVersionRepository,
        blob_repo: ContentBlobRepository,
        session_repo: ContentIngestSessionRepository,
        db_session: AsyncSession,
        content_dir: str,
    ) -> None:
        """Initialize the retention service with repositories and
        content directory.

        Parameters
        ----------
        corpus_repo : ContentCorpusRepository
            Repository for ``ContentCorpus`` entities.
        version_repo : ContentVersionRepository
            Repository for ``ContentVersion`` and ``ContentEntry``
            entities.
        blob_repo : ContentBlobRepository
            Repository for ``ContentBlob`` metadata.
        session_repo : ContentIngestSessionRepository
            Repository for ``IngestSession`` entities.
        db_session : AsyncSession
            SQLAlchemy async session for direct queries.
        content_dir : str
            Root directory of the content store.
        """
        self._corpus_repo = corpus_repo
        self._version_repo = version_repo
        self._blob_repo = blob_repo
        self._session_repo = session_repo
        self._db_session = db_session
        self._content_dir = Path(content_dir)
        self._blobs_dir = self._content_dir / "blobs"
        self._staging_dir = self._content_dir / "staging"

    async def collect_garbage(self) -> dict[str, int]:
        """Remove blobs not referenced by any retention-protected
        version and clean up aged-out ingestion sessions.

        The GC pass proceeds in four phases:

        1. **Identify protected versions** — collect all version IDs
           that have at least one :class:`VersionRunRef` or a
           :class:`ContentTag` with ``gc_protected=True``.
        2. **Compute reachable hashes** — collect every
           ``content_hash`` from the entries of all protected
           versions.
        3. **Purge unreferenced blobs** — remove blob metadata rows
           whose hash is not in the reachable set, then delete the
           corresponding on-disk files from
           ``<content_dir>/blobs/<aa>/<sha256>``.
        4. **Clean up expired sessions** — delete staging directories
           for sessions with ``FAILED`` status whose ``closed_at`` is
           older than 30 days.

        Returns
        -------
        dict of str → int
            A stats dictionary with the following keys:

            - ``blobs_removed``: number of blob metadata rows + disk
              files deleted.
            - ``versions_protected``: number of versions identified as
              retention-protected.
            - ``sessions_cleaned``: number of aged-out sessions whose
              staging area was removed.
        """
        protected: set[int] = set()

        run_ref_result = await self._db_session.execute(
            select(VersionRunRef.version_id).distinct()
        )
        for row in run_ref_result:
            protected.add(row[0])

        tag_result = await self._db_session.execute(
            select(ContentTag.version_id).where(ContentTag.gc_protected.is_(True))
        )
        for row in tag_result:
            protected.add(row[0])

        versions_protected = len(protected)

        keep_hashes: set[str] = set()
        for version_id in protected:
            entries = await self._version_repo.get_entries(version_id)
            for entry in entries:
                keep_hashes.add(entry.content_hash)

        all_hashes = await self._blob_repo.get_all_content_hashes()
        hashes_to_remove = set(all_hashes) - keep_hashes

        blobs_removed = 0
        if hashes_to_remove:
            db_count = await self._blob_repo.delete_unreferenced(keep_hashes)

            for h in hashes_to_remove:
                blob_path = self._blobs_dir / h[:2] / h
                if blob_path.exists():
                    blob_path.unlink()
                    blobs_removed += 1

            blobs_removed = max(blobs_removed, db_count)

        sessions_cleaned = 0
        cutoff = datetime.now() - timedelta(days=30)
        failed_sessions = await self._session_repo.list_by_status(IngestStatus.FAILED)

        for session in failed_sessions:
            if session.closed_at is not None and session.closed_at < cutoff:
                staging_area = self._staging_dir / session.staging_key
                if staging_area.exists():
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(
                        None, shutil.rmtree, str(staging_area), True
                    )
                sessions_cleaned += 1

        return {
            "blobs_removed": blobs_removed,
            "versions_protected": versions_protected,
            "sessions_cleaned": sessions_cleaned,
        }
