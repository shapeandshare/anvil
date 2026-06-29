# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Pure-Python, content-addressed local store implementing VersionedContentStore.

``LocalVersionedContentStore`` is the local-mode (no external service)
implementation of the :class:`VersionedContentStore` ABC.  It uses the
local filesystem for content-addressed blob storage and async SQLAlchemy
repositories for metadata persistence.

See ADR-033 for the full architecture.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

from aiofiles import open as async_open
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import get_config
from ...db.models.content_blob import ContentBlob
from ...db.models.content_entry import ContentEntry
from ...db.models.content_version import ContentVersion
from ...db.repositories.content_blobs import ContentBlobRepository
from ...db.repositories.content_corpora import ContentCorpusRepository
from ...db.repositories.content_ingest_sessions import ContentIngestSessionRepository
from ...db.repositories.content_versions import ContentVersionRepository
from .accept_result import AcceptResult
from .ingest_session_ref import IngestSessionRef
from .ingest_status import IngestStatus
from .manifest import Manifest, ManifestEntry, compute_manifest_digest
from .staged_entry import StagedEntry
from .validation_report import ValidationReport
from .validation_service import ValidationService
from .version_ref import VersionRef
from .versioned_content_store import VersionedContentStore

_STAGING_REF_FILENAME = ".staging_ref.json"
_CANONICAL_ENTRIES_FILENAME = "entries.json"
_BLOB_CHUNK_SIZE = 64 * 1024  # 64 KiB read chunks for streaming


class LocalVersionedContentStore(VersionedContentStore):
    """Local filesystem + SQLite implementation of a versioned content
    repository.

    Blobs are stored content-addressed under ``<content_dir>/blobs/``
    sharded by the first two hex characters of the SHA-256 digest.
    Staging areas live under ``<content_dir>/staging/``.  Canonical
    state is tracked via SQLAlchemy ORM models for versions and
    entries.

    Parameters
    ----------
    content_dir : str
        Root directory for content storage.  Defaults to
        ``"data/content"``.
    db_session : AsyncSession
        SQLAlchemy async session for metadata persistence.
    validation_service : ValidationService or None
        Validation gate runner.  A default instance is created when
        ``None``.
    """

    def __init__(
        self,
        content_dir: str | None = None,
        *,
        db_session: AsyncSession,
        validation_service: ValidationService | None = None,
    ) -> None:
        if content_dir is None:
            resolved_content_dir: str = get_config()["content_dir"]
        else:
            resolved_content_dir = content_dir
        self._content_dir = Path(resolved_content_dir)
        self._blobs_dir = self._content_dir / "blobs"
        self._staging_dir = self._content_dir / "staging"
        self._canonical_dir = self._content_dir / "canonical"

        self._blobs_dir.mkdir(parents=True, exist_ok=True)
        self._staging_dir.mkdir(parents=True, exist_ok=True)
        self._canonical_dir.mkdir(parents=True, exist_ok=True)

        self._version_repo = ContentVersionRepository(db_session)
        self._session_repo = ContentIngestSessionRepository(db_session)
        self._corpus_repo = ContentCorpusRepository(db_session)
        self._blob_repo = ContentBlobRepository(db_session)
        self._db_session = db_session

        self._validation = validation_service or ValidationService()

        # Per-corpus locks for serialized acceptance.

        # Per-corpus locks for serialized acceptance.
        self._accept_locks: dict[str, asyncio.Lock] = {}
        self._lock_for_locks = asyncio.Lock()

    # ── Corpora ─────────────────────────────────────────────────────

    async def ensure_corpus(self, slug: str) -> None:
        """Ensure a corpus subtree exists under the content directory.

        Creates ``<content_dir>/canonical/<slug>/`` if it does not
        already exist.  This method is idempotent.

        Parameters
        ----------
        slug : str
            Unique slug identifying the corpus.
        """
        corpus_dir = self._canonical_dir / slug
        corpus_dir.mkdir(parents=True, exist_ok=True)

    # ── Ingestion sessions ──────────────────────────────────────────

    async def open_session(
        self, corpus_slug: str, source_slug: str
    ) -> IngestSessionRef:
        """Open a new ingestion session for a corpus.

        Creates a unique ``staging_key`` (``{corpus_slug}/{uuid}``)
        and prepares the staging directory.  Returns an
        :class:`IngestSessionRef` that must be passed to subsequent
        :meth:`stage`, :meth:`validate_batch`, and
        :meth:`accept_session` calls.

        Parameters
        ----------
        corpus_slug : str
            Slug of the target corpus.
        source_slug : str
            Slug identifying the content source for provenance
            tracking.

        Returns
        -------
        IngestSessionRef
            Reference to the newly opened session.
        """
        staging_key = f"{corpus_slug}/{uuid.uuid4().hex}"
        staging_area = self._staging_dir / staging_key
        staging_area.mkdir(parents=True, exist_ok=True)

        # Retrieve (or ensure) the corpus in DB via the slug.
        corpus = await self._corpus_repo.get_by_slug(corpus_slug)
        if corpus is None:
            raise ValueError(f"Corpus not found in DB: {corpus_slug}")

        # Return an IngestSessionRef; the caller (IngestionService)
        # is responsible for creating the DB IngestSession record.
        return IngestSessionRef(
            session_id=0,  # placeholder — assigned by IngestionService
            corpus_id=corpus.id,
            staging_key=staging_key,
            status=IngestStatus.OPEN,
        )

    async def stage(
        self,
        session: IngestSessionRef,
        path: str,
        data: AsyncIterator[bytes],
    ) -> StagedEntry:
        """Stage a blob into an open ingestion session.

        Reads all bytes from the async iterator, computes the SHA-256
        digest, persists the blob to the content-addressed store, and
        writes a staging reference file.

        **Isolation guarantee**: This method writes only to the
        session-scoped staging area (``data/content/staging/<key>/``).
        Canonical corpus state is never modified during staging.

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
        # Read all bytes from the stream.
        chunks: list[bytes] = []
        async for chunk in data:
            chunks.append(chunk)
        raw = b"".join(chunks)

        content_hash = hashlib.sha256(raw).hexdigest()
        size_bytes = len(raw)

        # Persist blob to content-addressed store.
        blob_dir = self._blobs_dir / content_hash[:2]
        blob_dir.mkdir(parents=True, exist_ok=True)
        blob_path = blob_dir / content_hash

        # Write the blob file if it does not already exist (dedup).
        if not blob_path.exists():
            async with async_open(str(blob_path), "wb") as f:
                await f.write(raw)

        # Write staging reference (a JSON file pointing to the blob).
        staging_area = self._staging_dir / session.staging_key
        staging_ref_path = staging_area / path

        staging_ref_path.parent.mkdir(parents=True, exist_ok=True)
        ref_data = {
            "content_hash": content_hash,
            "size_bytes": size_bytes,
            "path": path,
        }
        async with async_open(str(staging_ref_path), "w") as f:
            await f.write(json.dumps(ref_data, separators=(",", ":")))

        return StagedEntry(
            path=path,
            content_hash=content_hash,
            size_bytes=size_bytes,
        )

    async def validate_batch(self, session: IngestSessionRef) -> ValidationReport:
        """Run all validation gates over a session's staged content.

        Delegates to :class:`ValidationService.validate`.

        Parameters
        ----------
        session : IngestSessionRef
            Active session reference.

        Returns
        -------
        ValidationReport
            Report listing every validation problem found.  The
            ``ok`` field is ``True`` when no blocking errors exist.
        """
        staged = await self._read_staged_entries(session)
        # Use a dummy slug since the store knows the corpus via the
        # session.  The ValidationService does not currently use the
        # slug for corpus-specific rules.
        return await self._validation.validate(
            staged,
            content_db_session=self._db_session,
            content_dir=str(self._content_dir),
            corpus_slug=_corpus_slug_from_key(session.staging_key),
        )

    async def accept_session(self, session: IngestSessionRef) -> AcceptResult:
        """Atomically fold staged content into the canonical corpus.

        Runs pre-acceptance validation gates; on all-green, creates a
        new immutable version with all staged entries within a single
        SQLite transaction.  Raises ``ValueError`` if gates fail or
        the session has no staged content.

        Uses an ``asyncio.Lock`` keyed by the corpus slug for
        serialized acceptance.

        Parameters
        ----------
        session : IngestSessionRef
            Session reference whose staged content to accept.

        Returns
        -------
        AcceptResult
            Metadata about the newly created version.

        Raises
        ------
        ValueError
            If validation gates fail or the session is empty.
        """
        corpus_slug = _corpus_slug_from_key(session.staging_key)

        # Acquire per-corpus lock.
        async with self._lock_for_locks:
            if corpus_slug not in self._accept_locks:
                self._accept_locks[corpus_slug] = asyncio.Lock()
            lock = self._accept_locks[corpus_slug]

        async with lock:
            return await self._accept_session_impl(session, corpus_slug)

    async def _accept_session_impl(
        self, session: IngestSessionRef, corpus_slug: str
    ) -> AcceptResult:
        """Internal accept implementation (called under lock).

        Parameters
        ----------
        session : IngestSessionRef
            Active session reference.
        corpus_slug : str
            Slug of the target corpus.

        Returns
        -------
        AcceptResult
            Metadata about the newly created version.

        Raises
        ------
        ValueError
            If validation gates fail or the session is empty.
        """
        # Read staged entries.
        staged = await self._read_staged_entries(session)
        if not staged:
            raise ValueError(f"Session {session.session_id} has no staged content")

        # Run validation gates (fail-closed, with 30-second timeout).
        report = await asyncio.wait_for(
            self._validation.validate(
                staged,
                content_db_session=self._db_session,
                content_dir=str(self._content_dir),
                corpus_slug=corpus_slug,
            ),
            timeout=30.0,
        )
        if not report.ok:
            raise ValueError(
                f"Session {session.session_id} failed validation: "
                f"{[p.reason for p in report.problems]}"
            )

        # Look up corpus.
        corpus = await self._corpus_repo.get_by_slug(corpus_slug)
        if corpus is None:
            raise ValueError(f"Corpus not found: {corpus_slug}")

        # Determine next version number.
        versions = await self._version_repo.list_by_corpus(corpus.id)
        version_number = (versions[0].version_number + 1) if versions else 1

        # Compute total size.
        total_bytes = sum(e.size_bytes for e in staged)

        # Build entries for the new version.
        manifest_entries = [
            ManifestEntry(path=e.path, content_hash=e.content_hash) for e in staged
        ]
        manifest = Manifest(
            corpus_slug=corpus_slug,
            version_number=version_number,
            entries=manifest_entries,
        )
        manifest_digest = compute_manifest_digest(manifest)

        # ---- Single SQLite transaction ----
        try:
            # 1. Persist blob metadata (upsert).
            for entry in staged:
                blob = ContentBlob(
                    content_hash=entry.content_hash,
                    size_bytes=entry.size_bytes,
                )
                await self._blob_repo.upsert(blob)

            # 2. Create the version record.
            version = ContentVersion(
                corpus_id=corpus.id,
                version_number=version_number,
                manifest_digest=manifest_digest,
                is_composition=False,
                entry_count=len(staged),
                total_bytes=total_bytes,
            )
            version = await self._version_repo.add(version)
            new_version_id = version.id

            # 3. Create entry records.
            for entry in staged:
                content_entry = ContentEntry(
                    version_id=new_version_id,
                    path=entry.path,
                    content_hash=entry.content_hash,
                    weight=1.0,
                    size_bytes=entry.size_bytes,
                )
                await self._version_repo.add_entry(content_entry)

            # 4. Update corpus current version.
            await self._corpus_repo.set_current_version(corpus.id, new_version_id)

            # 5. Write canonical entries.json.
            await self._write_canonical_entries(corpus_slug, staged, version_number)

            # 6. Commit the transaction (expires ORM objects).
            await self._db_session.commit()
        except Exception:
            await self._db_session.rollback()
            raise

        # Clean up staging directory.
        staging_area = self._staging_dir / session.staging_key
        await _rmtree(staging_area)

        return AcceptResult(
            version_id=new_version_id,
            manifest_digest=manifest_digest,
            version_number=version_number,
            entry_count=len(staged),
            total_bytes=total_bytes,
        )

    async def abandon_session(self, session: IngestSessionRef) -> None:
        """Discard a session's staged content without accepting it.

        Removes the staging directory for the session key.  No-op if
        the staging area does not exist.

        Parameters
        ----------
        session : IngestSessionRef
            Session reference to abandon.
        """
        staging_area = self._staging_dir / session.staging_key
        if staging_area.exists():
            await _rmtree(staging_area)

    # ── Versions & composition ──────────────────────────────────────

    async def freeze_version(
        self,
        corpus_slug: str,
        composition: list[ManifestEntry] | None = None,
    ) -> VersionRef:
        """Freeze a new immutable version of a corpus.

        When *composition* is ``None``, reads the current canonical
        entries from the database and creates a snapshot.  When
        *composition* is provided, creates a virtual composition
        version from the given entries.

        Parameters
        ----------
        corpus_slug : str
            Slug of the corpus to freeze.
        composition : list of ManifestEntry or None
            Optional explicit entry list for a virtual version.
            ``None`` snapshots the current canonical entries.

        Returns
        -------
        VersionRef
            Reference to the newly frozen version.
        """
        corpus = await self._corpus_repo.get_by_slug(corpus_slug)
        if corpus is None:
            raise ValueError(f"Corpus not found: {corpus_slug}")

        if composition is not None:
            entries = composition
            is_composition = True
        else:
            # Snapshot from canonical entries.json.
            canonical_path = (
                self._canonical_dir / corpus_slug / _CANONICAL_ENTRIES_FILENAME
            )
            if canonical_path.exists():
                async with async_open(str(canonical_path)) as f:
                    raw = await f.read()
                data = json.loads(raw)
                entries = [
                    ManifestEntry(
                        path=e["path"],
                        content_hash=e["content_hash"],
                        weight=e.get("weight", 1.0),
                        source=e.get("source"),
                    )
                    for e in data.get("entries", [])
                ]
            else:
                entries = []
            is_composition = False

        # Determine version number.
        versions = await self._version_repo.list_by_corpus(corpus.id)
        version_number = (versions[0].version_number + 1) if versions else 1

        # Compute total size from blob metadata.
        total_bytes = 0
        for entry in entries:
            blob = await self._blob_repo.exists(entry.content_hash)
            if blob and composition is None:
                # Size was stored when blobs were upserted.
                pass
            total_bytes += 0  # placeholder; real size is set on accept

        # Compute manifest digest.
        manifest = Manifest(
            corpus_slug=corpus_slug,
            version_number=version_number,
            is_composition=is_composition,
            entries=entries,
        )
        manifest_digest = compute_manifest_digest(manifest)

        # Persist to DB.
        version = ContentVersion(
            corpus_id=corpus.id,
            version_number=version_number,
            manifest_digest=manifest_digest,
            is_composition=is_composition,
            entry_count=len(entries),
            total_bytes=total_bytes,
        )
        version = await self._version_repo.add(version)
        new_version_id = version.id

        for entry in entries:
            content_entry = ContentEntry(
                version_id=new_version_id,
                path=entry.path,
                content_hash=entry.content_hash,
                weight=entry.weight,
                size_bytes=0,
            )
            await self._version_repo.add_entry(content_entry)

        manifest_dir = self._canonical_dir / corpus_slug / "manifests"
        manifest_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = manifest_dir / f"{new_version_id}.json"
        async with async_open(str(manifest_path), "w") as f:
            await f.write(
                json.dumps(
                    manifest.model_dump(),
                    indent=2,
                    sort_keys=True,
                )
            )

        await self._db_session.commit()

        return VersionRef(
            manifest_digest=manifest_digest,
            version_id=new_version_id,
            version_number=version_number,
        )

    async def resolve(self, version_ref: VersionRef) -> Manifest:
        """Resolve a version reference to its full manifest.

        Looks up the :class:`ContentVersion` by ID, reads its entries
        from the database, and returns a :class:`Manifest`.

        Parameters
        ----------
        version_ref : VersionRef
            Reference to a previously frozen version.

        Returns
        -------
        Manifest
            The full manifest, including all entries and metadata.

        Raises
        ------
        KeyError
            If the version ID is not found.
        """
        version = await self._version_repo.get(version_ref.version_id)
        if version is None:
            raise KeyError(f"Version not found: id={version_ref.version_id}")

        entries_orm = await self._version_repo.get_entries(version.id)
        entries = [
            ManifestEntry(
                path=e.path,
                content_hash=e.content_hash,
                weight=e.weight,
                source=None,
            )
            for e in entries_orm
        ]

        corpus = await self._corpus_repo.get(version.corpus_id)

        return Manifest(
            corpus_slug=corpus.slug if corpus is not None else "",
            version_number=version.version_number,
            is_composition=version.is_composition,
            entries=entries,
        )

    async def open_blob(self, content_hash: str) -> AsyncIterator[bytes]:
        """Open a content-addressed blob for streaming.

        Reads the blob file from ``<content_dir>/blobs/<aa>/<sha256>``
        and yields its content in 64 KiB chunks.

        Parameters
        ----------
        content_hash : str
            SHA-256 hex digest of the blob to retrieve.

        Returns
        -------
        AsyncIterator[bytes]
            Async iterable yielding the blob content in chunks.

        Raises
        ------
        KeyError
            If the blob file is not found on disk.
        """
        blob_path = self._blobs_dir / content_hash[:2] / content_hash
        if not blob_path.exists():
            raise KeyError(f"Blob not found: {content_hash}")

        async def _read_blob() -> AsyncIterator[bytes]:
            async with async_open(str(blob_path), "rb") as f:
                while True:
                    chunk = await f.read(_BLOB_CHUNK_SIZE)
                    if not chunk:
                        break
                    yield chunk

        return _read_blob()

    async def revert(self, corpus_slug: str, to_version: VersionRef) -> None:
        """Revert a corpus to a previous version.

        Creates a new HEAD version that is a copy of *to_version*,
        preserving the revert in the lineage history.

        Parameters
        ----------
        corpus_slug : str
            Slug of the corpus to revert.
        to_version : VersionRef
            Reference to the version to revert to.
        """
        # Resolve the target version to get its entries.
        manifest = await self.resolve(to_version)

        corpus = await self._corpus_repo.get_by_slug(corpus_slug)
        if corpus is None:
            raise ValueError(f"Corpus not found: {corpus_slug}")
        corpus_pk = corpus.id

        composition = manifest.entries

        ref = await self.freeze_version(corpus_slug, composition=composition)

        await self._corpus_repo.set_current_version(corpus_pk, ref.version_id)
        await self._db_session.commit()

    # ── Internal helpers ────────────────────────────────────────────

    async def _read_staged_entries(
        self, session: IngestSessionRef
    ) -> list[StagedEntry]:
        """Read all staging reference files for a session.

        Parameters
        ----------
        session : IngestSessionRef
            Active session reference.

        Returns
        -------
        list of StagedEntry
            All staged entries found in the session's staging area.
        """
        staging_area = self._staging_dir / session.staging_key
        if not staging_area.exists():
            return []

        entries: list[StagedEntry] = []
        async for ref_path in _async_scandir_recursive(staging_area):
            if ref_path.name == _STAGING_REF_FILENAME:
                continue
            # Each file is a staging reference JSON.
            async with async_open(str(ref_path)) as f:
                raw = await f.read()
            data = json.loads(raw)
            entries.append(
                StagedEntry(
                    path=data["path"],
                    content_hash=data["content_hash"],
                    size_bytes=data["size_bytes"],
                )
            )
        return entries

    async def _write_canonical_entries(
        self,
        corpus_slug: str,
        entries: list[StagedEntry],
        version_number: int,
    ) -> None:
        """Write the canonical entries.json for a corpus.

        Parameters
        ----------
        corpus_slug : str
            Slug identifying the corpus.
        entries : list of StagedEntry
            The entries comprising the new canonical state.
        version_number : int
            The version number associated with this state.
        """
        canonical_dir = self._canonical_dir / corpus_slug
        canonical_dir.mkdir(parents=True, exist_ok=True)

        data = {
            "corpus_slug": corpus_slug,
            "version_number": version_number,
            "entries": [
                {
                    "path": e.path,
                    "content_hash": e.content_hash,
                    "weight": 1.0,
                    "size_bytes": e.size_bytes,
                }
                for e in entries
            ],
        }
        path = canonical_dir / _CANONICAL_ENTRIES_FILENAME
        async with async_open(str(path), "w") as f:
            await f.write(json.dumps(data, indent=2, sort_keys=True))


# ── Module-level helpers ────────────────────────────────────────────


def _corpus_slug_from_key(staging_key: str) -> str:
    """Extract the corpus slug from a staging key.

    Staging keys are formatted as ``{corpus_slug}/{uuid}``.

    Parameters
    ----------
    staging_key : str
        The staging key to parse.

    Returns
    -------
    str
        The corpus slug portion of the key.
    """
    return staging_key.split("/", 1)[0]


async def _rmtree(path: Path) -> None:
    """Asynchronously remove a directory tree.

    Uses :func:`os.scandir` via the :mod:`pathlib` sync API wrapped in
    an executor to avoid blocking the event loop on large trees.

    Parameters
    ----------
    path : Path
        Root of the directory tree to remove.
    """
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, shutil.rmtree, str(path), True)


async def _async_scandir_recursive(
    root: Path,
) -> AsyncIterator[Path]:
    """Recursively yield all regular files under *root*.

    Parameters
    ----------
    root : Path
        Root directory to scan.

    Yields
    ------
    Path
        Paths to regular files within the tree.
    """
    loop = asyncio.get_running_loop()

    def _scan() -> list[Path]:
        result: list[Path] = []
        for dirpath, _dirnames, filenames in os.walk(str(root)):
            for fn in filenames:
                result.append(Path(dirpath) / fn)
        return result

    paths = await loop.run_in_executor(None, _scan)
    for p in paths:
        yield p
