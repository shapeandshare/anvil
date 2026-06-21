"""Ingestion session orchestration service.

``IngestionService`` coordinates the lifecycle of content ingestion
sessions: opening, staging, validating, accepting, and abandoning.
It delegates content-addressed storage to a
:class:`VersionedContentStore` implementation, manages the session
metadata via repositories, and enforces validation gates.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Sequence

from ...db.models.content_ingest_session import IngestSession
from ...db.repositories.content_blobs import ContentBlobRepository
from ...db.repositories.content_corpora import ContentCorpusRepository
from ...db.repositories.content_ingest_sessions import ContentIngestSessionRepository
from ...db.repositories.content_sources import ContentSourceRepository
from ...db.repositories.content_versions import ContentVersionRepository
from .accept_result import AcceptResult
from .ingest_session_ref import IngestSessionRef
from .ingest_status import IngestStatus
from .staged_entry import StagedEntry
from .validation_report import ValidationReport
from .validation_service import ValidationService
from .versioned_content_store import VersionedContentStore

_logger = logging.getLogger(__name__)


class IngestionService:
    """Orchestrates content ingestion session lifecycle.

    Parameters
    ----------
    session_repo : ContentIngestSessionRepository
        Repository for ``IngestSession`` entities.
    version_repo : ContentVersionRepository
        Repository for ``ContentVersion`` and ``ContentEntry``
        entities.
    blob_repo : ContentBlobRepository
        Repository for ``ContentBlob`` metadata.
    corpus_repo : ContentCorpusRepository
        Repository for ``ContentCorpus`` entities.
    source_repo : ContentSourceRepository
        Repository for ``ContentSource`` entities.
    content_store : VersionedContentStore
        The content-addressed blob store implementation.
    validation_service : ValidationService
        Validation gate runner for pre-acceptance checks.
    """

    def __init__(
        self,
        session_repo: ContentIngestSessionRepository,
        version_repo: ContentVersionRepository,
        blob_repo: ContentBlobRepository,
        corpus_repo: ContentCorpusRepository,
        source_repo: ContentSourceRepository,
        content_store: VersionedContentStore,
        validation_service: ValidationService,
    ) -> None:
        self._session_repo = session_repo
        self._version_repo = version_repo
        self._blob_repo = blob_repo
        self._corpus_repo = corpus_repo
        self._source_repo = source_repo
        self._content_store = content_store
        self._validation = validation_service

    async def open_session(self, corpus_id: int, source_id: int) -> IngestSessionRef:
        """Open a new ingestion session.

        Looks up the corpus and source by their primary keys,
        delegates staging-area creation to the content store, and
        persists a new ``IngestSession`` record in the database.

        Parameters
        ----------
        corpus_id : int
            Primary key of the target corpus.
        source_id : int
            Primary key of the content source.

        Returns
        -------
        IngestSessionRef
            Reference to the newly opened session, with a valid
            ``session_id`` populated from the database.

        Raises
        ------
        ValueError
            If the corpus or source is not found.
        """
        corpus = await self._corpus_repo.get(corpus_id)
        if corpus is None:
            raise ValueError(f"Corpus not found: {corpus_id}")

        source = await self._source_repo.get(source_id)
        if source is None:
            raise ValueError(f"Source not found: {source_id}")

        store_ref = await self._content_store.open_session(corpus.slug, source.slug)

        db_session = IngestSession(
            corpus_id=corpus.id,
            source_id=source.id,
            staging_key=store_ref.staging_key,
            status=IngestStatus.OPEN,
        )
        db_session = await self._session_repo.add(db_session)

        return IngestSessionRef(
            session_id=db_session.id,
            corpus_id=corpus.id,
            staging_key=store_ref.staging_key,
            status=IngestStatus.OPEN,
        )

    async def _assert_session_scope(
        self,
        session_id: int,
        caller_identity: str | None = None,
    ) -> None:
        """Assert that the caller is scoped to the given session.

        This is the authorization injection seam for multi-principal
        RBAC (FR-036) in the future SaaS delivery.  In local single-user
        mode, any local operator owns all sessions, so the guard passes
        trivially after verifying the session exists.

        Parameters
        ----------
        session_id : int
            Primary key of the target session.
        caller_identity : str or None
            Caller identity string (e.g. user ID, API key owner).
            ``None`` in local mode — ignored; reserved for SaaS
            org/team/role checks.

        Raises
        ------
        ValueError
            If the session does not exist.
        """
        db_session = await self._session_repo.get(session_id)
        if db_session is None:
            raise ValueError(f"Session not found: {session_id}")

        # Local single-user mode: any local user is trivially scoped.
        # Future SaaS: inject org/team/role check against caller_identity.

    async def stage(
        self,
        session_id: int,
        path: str,
        data_stream: AsyncIterator[bytes],
    ) -> StagedEntry:
        """Stage a blob into an open ingestion session.

        Delegates blob storage and staging reference creation to the
        content store, then increments the ``staged_entry_count`` on
        the session's DB record.

        **Isolation guarantee**: This method writes only to the
        session-scoped staging area (identified by the session's
        ``staging_key``).  Canonical corpus state is never modified
        during staging (only :meth:`accept` mutates canonical).

        Parameters
        ----------
        session_id : int
            Primary key of the target session.
        path : str
            Relative path for the entry within the session.
        data_stream : AsyncIterator[bytes]
            Async iterable yielding the blob content in chunks.

        Returns
        -------
        StagedEntry
            Metadata for the staged blob, including its content hash
            and size.

        Raises
        ------
        ValueError
            If the session is not found or not in ``OPEN`` status.
        """
        await self._assert_session_scope(session_id)

        db_session = await self._session_repo.get(session_id)
        if db_session is None:
            raise ValueError(f"Session not found: {session_id}")
        if db_session.status != IngestStatus.OPEN:
            raise ValueError(
                f"Session {session_id} is not open " f"(status={db_session.status})"
            )

        session_ref = IngestSessionRef(
            session_id=db_session.id,
            corpus_id=db_session.corpus_id,
            staging_key=db_session.staging_key,
            status=db_session.status,
        )

        staged = await self._content_store.stage(session_ref, path, data_stream)

        await self._session_repo.update_status(session_id, IngestStatus.OPEN)

        return staged

    async def validate(self, session_id: int) -> ValidationReport:
        """Run validation gates over a session's staged content.

        Delegates to ``content_store.validate_batch``, which in turn
        delegates to :class:`ValidationService`.

        Parameters
        ----------
        session_id : int
            Primary key of the session to validate.

        Returns
        -------
        ValidationReport
            Report listing every validation problem found.  The
            ``ok`` field is ``True`` when no blocking errors exist.

        Raises
        ------
        ValueError
            If the session is not found.
        """
        db_session = await self._session_repo.get(session_id)
        if db_session is None:
            raise ValueError(f"Session not found: {session_id}")

        await self._session_repo.update_status(session_id, IngestStatus.VALIDATING)

        session_ref = IngestSessionRef(
            session_id=db_session.id,
            corpus_id=db_session.corpus_id,
            staging_key=db_session.staging_key,
            status=IngestStatus.VALIDATING,
        )

        return await self._content_store.validate_batch(session_ref)

    async def accept(self, session_id: int) -> AcceptResult:
        """Accept a session's staged content.

        Runs pre-acceptance validation gates first, then delegates to
        ``content_store.accept_session`` to atomically fold content
        into the canonical corpus.  On success, updates the session
        status to ``ACCEPTED`` and records the new version ID.

        **Fail-closed**: If validation fails or the store raises any
        exception, the session is marked ``FAILED`` and the structured
        problems (or error message) are persisted to
        ``problems_json``.

        Parameters
        ----------
        session_id : int
            Primary key of the session to accept.

        Returns
        -------
        AcceptResult
            Metadata about the newly created version.

        Raises
        ------
        ValueError
            If the session is not found, validation fails, or the
            store encounters an unexpected error.
        """
        db_session = await self._session_repo.get(session_id)
        if db_session is None:
            raise ValueError(f"Session not found: {session_id}")

        session_ref = IngestSessionRef(
            session_id=db_session.id,
            corpus_id=db_session.corpus_id,
            staging_key=db_session.staging_key,
            status=db_session.status,
        )

        # Run validation gates first to capture structured problems.
        report = await self.validate(session_id)
        if not report.ok:
            problems_json = json.dumps([p.model_dump() for p in report.problems])
            await self._session_repo.update_status(
                session_id, IngestStatus.FAILED, problems=problems_json
            )
            raise ValueError(
                f"Session {session_id} failed validation: "
                f"{[p.reason for p in report.problems]}"
            )

        # Proceed with store-level acceptance (also runs validation
        # as a belt-and-suspenders check).
        try:
            result = await self._content_store.accept_session(session_ref)
        except ValueError:
            # Persist the failure without structured problems (the
            # store raised its own error for empty session, etc.).
            db_s = await self._session_repo.get(session_id)
            if db_s is not None:
                await self._session_repo.update_status(session_id, IngestStatus.FAILED)
            raise
        except Exception as exc:
            _logger.exception("Validation gate failed unexpectedly.")
            db_s = await self._session_repo.get(session_id)
            if db_s is not None:
                await self._session_repo.update_status(session_id, IngestStatus.FAILED)
            raise ValueError("Validation gate failed unexpectedly.") from exc

        await self._session_repo.update_status(session_id, IngestStatus.ACCEPTED)
        await self._session_repo.set_accepted_version(session_id, result.version_id)

        return result

    async def abandon(self, session_id: int) -> None:
        """Abandon a session and fail it.

        Delegates staging-area cleanup to the content store and marks
        the session as ``FAILED`` in the database.

        Parameters
        ----------
        session_id : int
            Primary key of the session to abandon.

        Raises
        ------
        ValueError
            If the session is not found.
        """
        db_session = await self._session_repo.get(session_id)
        if db_session is None:
            raise ValueError(f"Session not found: {session_id}")

        session_ref = IngestSessionRef(
            session_id=db_session.id,
            corpus_id=db_session.corpus_id,
            staging_key=db_session.staging_key,
            status=db_session.status,
        )

        await self._content_store.abandon_session(session_ref)
        await self._session_repo.update_status(session_id, IngestStatus.FAILED)

    async def list_active(self) -> Sequence[IngestSession]:
        """List all currently active (non-terminal) ingestion sessions.

        Returns
        -------
        Sequence of IngestSession
            Active ``IngestSession`` records, ordered by creation date
            descending.
        """
        return await self._session_repo.list_active()
