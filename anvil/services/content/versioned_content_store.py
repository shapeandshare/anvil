"""Abstract interface for the versioned content repository.

``VersionedContentStore`` defines the contract for a versioned,
content-addressed blob store with immutable version pinning,
concurrent isolated ingestion, automated validation gates,
weighted composition, and lineage tracking.

Local mode uses a pure-Python implementation over
:class:`LocalFileStore <anvil.storage.local_file_store.LocalFileStore>`
+ SQLite. SaaS mode uses a LakeFS-backed implementation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from .accept_result import AcceptResult
from .ingest_session_ref import IngestSessionRef
from .manifest import Manifest, ManifestEntry
from .staged_entry import StagedEntry
from .validation_report import ValidationReport
from .version_ref import VersionRef


class VersionedContentStore(ABC):
    """Abstract versioned content repository.

    Implementations provide content-addressed blob storage with
    immutable version pinning, concurrent isolated ingestion sessions,
    automated validation gates, weighted composition across corpora,
    and full lineage tracking.

    All public methods are async (Article V).
    """

    @abstractmethod
    async def ensure_corpus(self, slug: str) -> None:
        """Ensure a corpus exists, creating it if necessary.

        Parameters
        ----------
        slug : str
            Unique slug identifying the corpus. Must match
            ``[a-z][a-z0-9_-]*``.
        """
        ...

    @abstractmethod
    async def open_session(
        self, corpus_slug: str, source_slug: str
    ) -> IngestSessionRef:
        """Open a new ingestion session for a corpus.

        Parameters
        ----------
        corpus_slug : str
            Slug of the target corpus.
        source_slug : str
            Slug identifying the content source (e.g. injector or
            importer name) for provenance tracking.

        Returns
        -------
        IngestSessionRef
            Reference to the newly opened session.
        """
        ...

    @abstractmethod
    async def stage(
        self,
        session: IngestSessionRef,
        path: str,
        data: AsyncIterator[bytes],
    ) -> StagedEntry:
        """Stage a blob into an open ingestion session.

        Parameters
        ----------
        session : IngestSessionRef
            Active session reference from :meth:`open_session`.
        path : str
            Relative path for the entry within the session.
        data : AsyncIterator[bytes]
            Async iterable yielding the blob content in chunks.

        Returns
        -------
        StagedEntry
            Metadata for the staged blob, including its content hash
            and size.
        """
        ...

    @abstractmethod
    async def validate_batch(self, session: IngestSessionRef) -> ValidationReport:
        """Run all validation gates over a session's staged content.

        Parameters
        ----------
        session : IngestSessionRef
            Active session reference.

        Returns
        -------
        ValidationReport
            Report listing every validation problem found. The
            ``ok`` field is ``True`` when no blocking errors exist.
        """
        ...

    @abstractmethod
    async def accept_session(self, session: IngestSessionRef) -> AcceptResult:
        """Atomically fold staged content into the canonical corpus.

        Creates a new immutable version snapshot containing all
        staged entries. The session must have passed validation
        (``validate_batch().ok is True``).

        Parameters
        ----------
        session : IngestSessionRef
            Session reference whose staged content to accept.

        Returns
        -------
        AcceptResult
            Metadata about the newly created version.
        """
        ...

    @abstractmethod
    async def abandon_session(self, session: IngestSessionRef) -> None:
        """Discard a session's staged content without accepting it.

        Parameters
        ----------
        session : IngestSessionRef
            Session reference to abandon.
        """
        ...

    @abstractmethod
    async def freeze_version(
        self,
        corpus_slug: str,
        composition: list[ManifestEntry] | None = None,
    ) -> VersionRef:
        """Freeze a new immutable version of a corpus.

        When *composition* is ``None``, snapshots the current HEAD.
        When *composition* is provided, creates a virtual composition
        version from the given entries (which may reference blobs
        from multiple corpora).

        Parameters
        ----------
        corpus_slug : str
            Slug of the corpus to freeze.
        composition : list[ManifestEntry] | None
            Optional explicit entry list for a virtual version.
            ``None`` snapshots the current HEAD.

        Returns
        -------
        VersionRef
            Reference to the newly frozen version.
        """
        ...

    @abstractmethod
    async def resolve(self, version_ref: VersionRef) -> Manifest:
        """Resolve a version reference to its full manifest.

        Parameters
        ----------
        version_ref : VersionRef
            Reference to a previously frozen version.

        Returns
        -------
        Manifest
            The full manifest, including all entries and metadata.
        """
        ...

    @abstractmethod
    async def open_blob(self, content_hash: str) -> AsyncIterator[bytes]:
        """Open a content-addressed blob for streaming.

        Parameters
        ----------
        content_hash : str
            SHA-256 hex digest of the blob to retrieve.

        Returns
        -------
        AsyncIterator[bytes]
            Async iterable yielding the blob content in chunks.
        """
        ...

    @abstractmethod
    async def revert(self, corpus_slug: str, to_version: VersionRef) -> None:
        """Revert a corpus to a previous version.

        Creates a new HEAD that is a copy of *to_version*,
        preserving the revert in the lineage history.

        Parameters
        ----------
        corpus_slug : str
            Slug of the corpus to revert.
        to_version : VersionRef
            Reference to the version to revert to.
        """
        ...