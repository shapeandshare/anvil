"""Advisory checks and post-acceptance maintenance for content versions.

``AdvisoryService`` provides non-blocking advisory checks
(FR-015) and post-acceptance refresh operations (FR-026a) for
immutable content versions in the Content Repository (016).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from ...db.repositories.content_blobs import ContentBlobRepository
    from ...db.repositories.content_ingest_sessions import (
        ContentIngestSessionRepository,
    )
    from ...db.repositories.content_versions import ContentVersionRepository

logger = logging.getLogger(__name__)


class AdvisoryService:
    """Non-blocking advisory checks and post-acceptance version maintenance.

    Provides three categories of post-acceptance operations:

    1. **Near-duplicate detection** (FR-015) — cross-version exact hash
       comparison within the same corpus, returning advisory flags.
    2. **Derived-state refresh** (FR-026a) — placeholder for re-chunking
       and re-tokenization; currently records a note on the version.
    3. **Acceptance statistics** (FR-026a) — records entry count, total
       byte size, and timestamp for a version via logging and JSON output.

    All operations are **advisory** — they never block or reject.

    Parameters
    ----------
    version_repo : ContentVersionRepository
        Repository for version metadata and entry access.
    session_repo : ContentIngestSessionRepository
        Repository for ingest session metadata (reserved for future use).
    blob_repo : ContentBlobRepository
        Repository for blob metadata (reserved for future use).
    db_session : AsyncSession
        SQLAlchemy async session for direct queries.
    """

    def __init__(
        self,
        version_repo: ContentVersionRepository,
        session_repo: ContentIngestSessionRepository,
        blob_repo: ContentBlobRepository,
        db_session: AsyncSession,
    ) -> None:
        self._version_repo = version_repo
        self._session_repo = session_repo
        self._blob_repo = blob_repo
        self._db_session = db_session

    async def detect_near_duplicates(self, version_id: int) -> list[dict[str, Any]]:
        """Detect near-duplicate entries across versions in the same corpus.

        Compares each entry's ``content_hash`` against entries from other
        versions of the **same corpus** (excluding the current version).
        Entries whose content hash already exists elsewhere are flagged as
        advisory duplicates.

        This is a non-blocking advisory check (FR-015) — the caller may
        choose to investigate or ignore the results.

        Parameters
        ----------
        version_id : int
            Primary key of the ``ContentVersion`` to analyse.

        Returns
        -------
        list of dict
            A list of flag dicts, each with:
            - ``entry_path`` (str): path of the entry in the current
              version.
            - ``duplicate_path`` (str): path of the pre-existing entry
              found in another version.
            - ``duplicate_version_id`` (int): primary key of the version
              that already contains this content.

            Returns an empty list when no cross-version duplicates are
            found or when *version_id* does not exist.

        Notes
        -----
        Because ``ContentEntry`` is linked to ``ContentVersion`` via a
        foreign key and ``ContentVersion`` has a ``corpus_id``, a single
        SQLAlchemy query with a join is used to locate duplicates within
        the same corpus across different versions.
        """
        version = await self._version_repo.get(version_id)
        if version is None:
            return []

        entries = await self._version_repo.get_entries(version_id)
        if not entries:
            return []

        current_hashes = {e.content_hash for e in entries}
        if not current_hashes:
            return []

        from ...db.models.content_entry import ContentEntry
        from ...db.models.content_version import ContentVersion

        result = await self._db_session.execute(
            select(ContentEntry)
            .join(ContentVersion, ContentEntry.version_id == ContentVersion.id)
            .where(
                ContentVersion.corpus_id == version.corpus_id,
                ContentEntry.version_id != version_id,
                ContentEntry.content_hash.in_(current_hashes),
            )
        )
        duplicate_entries = result.scalars().all()

        dup_lookup: dict[str, tuple[str, int]] = {}
        for dup_entry in duplicate_entries:
            if dup_entry.content_hash not in dup_lookup:
                dup_lookup[dup_entry.content_hash] = (
                    dup_entry.path,
                    dup_entry.version_id,
                )

        duplicates: list[dict[str, Any]] = []
        for entry in entries:
            match = dup_lookup.get(entry.content_hash)
            if match is not None:
                duplicates.append(
                    {
                        "entry_path": entry.path,
                        "duplicate_path": match[0],
                        "duplicate_version_id": match[1],
                    }
                )

        return duplicates

    async def refresh_derived_state(self, version_id: int) -> None:
        """Post-acceptance placeholder for derived-state refresh.

        In a future iteration this method will re-chunk and re-tokenize
        the version's content.  For now it is a no-op that records a
        refresh note on the version's ``note`` field in the database
        (FR-026a).

        Parameters
        ----------
        version_id : int
            Primary key of the ``ContentVersion`` to refresh.
        """
        version = await self._version_repo.get(version_id)
        if version is None:
            logger.warning(
                "refresh_derived_state: version_id=%s not found, skipping",
                version_id,
            )
            return

        timestamp = datetime.now(UTC).isoformat()
        note_suffix = (
            f"[derived-state refresh requested at {timestamp}] — "
            f"no-op placeholder (FR-026a)"
        )

        if version.note:
            version.note = f"{version.note}\n{note_suffix}"
        else:
            version.note = note_suffix

        await self._db_session.flush()
        logger.info(
            "refresh_derived_state: recorded refresh note on " "version_id=%s",
            version_id,
        )

    async def record_acceptance_stats(self, version_id: int) -> None:
        """Record acceptance statistics for a content version.

        Computes entry count and total byte size from the version's
        entries, updates the version metadata in the database, logs
        the statistics, and writes a JSON advisory record to the
        content store's advisory directory (FR-026a).

        Parameters
        ----------
        version_id : int
            Primary key of the ``ContentVersion`` to record statistics
            for.
        """
        version = await self._version_repo.get(version_id)
        if version is None:
            logger.warning(
                "record_acceptance_stats: version_id=%s not found, skipping",
                version_id,
            )
            return

        entries = await self._version_repo.get_entries(version_id)
        entry_count = len(entries)
        total_bytes = sum(e.size_bytes for e in entries)
        timestamp = datetime.now(UTC).isoformat()

        version.entry_count = entry_count
        version.total_bytes = total_bytes

        stats = {
            "version_id": version_id,
            "corpus_id": version.corpus_id,
            "version_number": version.version_number,
            "entry_count": entry_count,
            "total_bytes": total_bytes,
            "timestamp": timestamp,
        }

        logger.info(
            "Acceptance stats for version_id=%s (corpus=%s, v%s): "
            "%s entries, %s bytes",
            version_id,
            version.corpus_id,
            version.version_number,
            entry_count,
            total_bytes,
        )

        from ...config import get_config

        content_dir = get_config()["content_dir"]
        advisory_dir = Path(content_dir) / "advisory"
        advisory_dir.mkdir(parents=True, exist_ok=True)
        stats_file = advisory_dir / f"acceptance-{version_id}.json"
        stats_file.write_text(json.dumps(stats, indent=2))

        await self._db_session.flush()
        logger.info(
            "record_acceptance_stats: wrote advisory JSON to %s",
            stats_file,
        )
