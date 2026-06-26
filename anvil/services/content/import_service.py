"""Declarative content import job orchestration.

``ImportService`` coordinates the lifecycle of declarative import
jobs: starting a new job (which opens an underlying ingestion
session), tracking status, and managing the job-to-session
relationship.  Each job declares a configuration for pulling content
from an external source into a corpus via the existing
:class:`IngestionService` validation gates.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from typing import Any

from ...db.models.content_import_job import ImportJob
from ...db.repositories.content_corpora import ContentCorpusRepository
from ...db.repositories.content_import_jobs import ContentImportJobRepository
from ...db.repositories.content_ingest_sessions import ContentIngestSessionRepository
from ...db.repositories.content_sources import ContentSourceRepository
from .ingestion_service import IngestionService
from .versioned_content_store import VersionedContentStore

_logger = logging.getLogger(__name__)


class ImportService:
    """Orchestrates declarative import jobs for the content repository.

    Each import job declares a configuration for pulling content from
    an external source (identified by slug) into a target corpus.  The
    service opens an ``IngestionService`` session on the job's behalf
    so that all staged content passes through the same validation
    gates before acceptance.

    Parameters
    ----------
    import_job_repo : ContentImportJobRepository
        Repository for ``ImportJob`` entities.
    session_repo : ContentIngestSessionRepository
        Repository for ``IngestSession`` entities.
    source_repo : ContentSourceRepository
        Repository for ``ContentSource`` entities.
    corpus_repo : ContentCorpusRepository
        Repository for ``ContentCorpus`` entities.
    content_store : VersionedContentStore
        The content-addressed blob store implementation.
    ingestion_service : IngestionService
        The ingestion orchestration service used to open sessions,
        stage content, and run validation gates.
    """

    def __init__(
        self,
        import_job_repo: ContentImportJobRepository,
        session_repo: ContentIngestSessionRepository,
        source_repo: ContentSourceRepository,
        corpus_repo: ContentCorpusRepository,
        content_store: VersionedContentStore,
        ingestion_service: IngestionService,
    ) -> None:
        self._import_repo = import_job_repo
        self._session_repo = session_repo
        self._source_repo = source_repo
        self._corpus_repo = corpus_repo
        self._content_store = content_store
        self._ingestion = ingestion_service

    async def start(
        self,
        corpus_id: int,
        source_slug: str,
        config: dict[str, Any],
    ) -> ImportJob:
        """Start a new declarative import job.

        Looks up the source by its slug and the corpus by its primary
        key, opens an ingestion session through the
        ``IngestionService``, and persists a new ``ImportJob`` record
        linked to the session.

        Parameters
        ----------
        corpus_id : int
            Primary key of the target corpus.
        source_slug : str
            Unique slug identifying the content source.
        config : dict
            Job-specific configuration (e.g. filter patterns, path
            mappings, chunking overrides).  Serialised to JSON for
            storage in the ``ImportJob.config_json`` field.

        Returns
        -------
        ImportJob
            The newly persisted ``ImportJob`` instance with its
            generated primary key and linked session ID populated.

        Raises
        ------
        ValueError
            If the source slug is unknown or the corpus is not found.
        """
        source = await self._source_repo.get_by_slug(source_slug)
        if source is None:
            raise ValueError(f"Content source not found: '{source_slug}'")

        corpus = await self._corpus_repo.get(corpus_id)
        if corpus is None:
            raise ValueError(f"Corpus not found: {corpus_id}")

        # Open an ingest session (content goes through same validation
        # gates as direct staging).
        session_ref = await self._ingestion.open_session(corpus_id, source.id)

        # Create import job record linked to the session.
        job = ImportJob(
            corpus_id=corpus_id,
            source_id=source.id,
            config_json=json.dumps(config),
            session_id=session_ref.session_id,
        )
        job = await self._import_repo.add(job)
        _logger.info(
            "Created import job %d for corpus %d source '%s' (session %d)",
            job.id,
            corpus_id,
            source_slug,
            session_ref.session_id,
        )
        return job

    async def status(self, job_id: int) -> ImportJob | None:
        """Retrieve the current status of an import job.

        Parameters
        ----------
        job_id : int
            Primary key of the job to query.

        Returns
        -------
        ImportJob | None
            The matching ``ImportJob`` instance, or ``None`` if no
            record exists with the given ``id``.
        """
        return await self._import_repo.get(job_id)

    async def list(self) -> Sequence[ImportJob]:
        """Retrieve all import jobs ordered by creation time (newest
        first).

        Returns
        -------
        Sequence[ImportJob]
            All persisted ``ImportJob`` records.
        """
        return await self._import_repo.get_all()
