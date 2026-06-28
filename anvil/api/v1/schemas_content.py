# Copyright © 2026 Josh Burt
# one-class:allow — intentional domain grouping of tightly coupled content schemas
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Request/response models for content repository API endpoints.

Pure Pydantic ``BaseModel`` subclasses used for versioned content
corpora, ingestion sessions, version management, and training-data
composition endpoints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ContentCorpusCreate(BaseModel):
    """Request body for creating a new versioned content corpus.

    Parameters
    ----------
    name : str
        Human-readable corpus name.
    slug : str | None, optional
        Unique machine-readable identifier. Auto-generated from *name*
        when ``None``. Defaults to ``None``.
    description : str | None, optional
        Optional description. Defaults to ``None``.
    chunking_strategy : str, optional
        Chunking algorithm (``"windowed"``, ``"file"``, or ``"line"``).
        Defaults to ``"windowed"``.
    block_size : int, optional
        Token block size for windowed chunking. Defaults to ``16``.
    chunk_overlap : float, optional
        Fractional overlap between chunks. Defaults to ``0.5``.
    declared_source : str | None, optional
        Provenance source description. Defaults to ``None``.
    license : str | None, optional
        Approved license identifier. Defaults to ``None``.
    attribution : str | None, optional
        Required attribution text. Defaults to ``None``.
    """

    name: str
    slug: str | None = None
    description: str | None = None
    chunking_strategy: str = "windowed"
    block_size: int = 16
    chunk_overlap: float = 0.5
    declared_source: str | None = None
    license: str | None = None
    attribution: str | None = None


class ContentCorpusOut(BaseModel):
    """Content corpus as returned by the API.

    Parameters
    ----------
    id : int
        Primary key.
    slug : str
        Unique machine-readable identifier.
    name : str
        Human-readable name.
    description : str | None, optional
        Optional description.
    chunking_strategy : str
        Chunking algorithm name.
    block_size : int
        Token block size.
    chunk_overlap : float
        Fractional overlap between chunks.
    status : str
        Lifecycle status from ``ContentCorpusStatus``.
    file_count : int
        Number of files in the corpus.
    document_count : int
        Number of chunked documents.
    created_at : datetime
        Row creation timestamp.
    """

    id: int
    slug: str
    name: str
    description: str | None = None
    chunking_strategy: str
    block_size: int
    chunk_overlap: float
    status: str
    file_count: int
    document_count: int
    created_at: datetime


class ContentVersionOut(BaseModel):
    """Immutable version snapshot as returned by the API.

    Parameters
    ----------
    id : int
        Primary key.
    corpus_id : int
        FK to the parent corpus.
    version_number : int
        Monotonically increasing version number within the corpus.
    manifest_digest : str
        SHA-256 hex digest of the manifest.
    label : str | None, optional
        Optional human-readable label.
    entry_count : int
        Number of entries in this version.
    total_bytes : int
        Total blob size across all entries.
    tag : str | None, optional
        Optional tag name (FR-023). Defaults to ``None``.
    created_at : datetime
        Row creation timestamp.
    """

    id: int
    corpus_id: int
    version_number: int
    manifest_digest: str
    label: str | None = None
    entry_count: int
    total_bytes: int
    tag: str | None = None
    created_at: datetime


class SessionOpenBody(BaseModel):
    """Request body for opening a new ingestion session.

    Parameters
    ----------
    corpus_id : int
        FK of the target corpus.
    source : str
        Source slug identifying the content origin.
    """

    corpus_id: int
    source: str


class SessionOut(BaseModel):
    """Ingestion session as returned by the API.

    Parameters
    ----------
    id : int
        Primary key.
    corpus_id : int
        FK to the parent corpus.
    source_id : int
        FK to the content source.
    status : str
        Current session status from ``IngestStatus``.
    staged_entry_count : int
        Number of entries staged so far.
    problems_json : str | None, optional
        JSON-serialised validation problems.
    opened_at : datetime
        Timestamp when the session was opened.
    """

    id: int
    corpus_id: int
    source_id: int
    status: str
    staged_entry_count: int = 0
    problems_json: str | None = None
    opened_at: datetime


class AcceptOut(BaseModel):
    """Outcome of accepting a staged ingestion session.

    Parameters
    ----------
    version_id : int
        Internal version identifier for the new snapshot.
    manifest_digest : str
        SHA-256 hex digest of the produced manifest.
    version_number : int
        Monotonically increasing version number.
    entry_count : int
        Number of entries folded into the corpus.
    total_bytes : int
        Total blob size across all accepted entries.
    """

    version_id: int
    manifest_digest: str
    version_number: int
    entry_count: int
    total_bytes: int


class ValidationReportOut(BaseModel):
    """Validation report as returned by the API.

    Parameters
    ----------
    ok : bool
        ``True`` when no blocking validation problems were found.
    problems : list[dict]
        List of validation problem dicts.
    """

    ok: bool
    problems: list[dict[str, Any]] = []


class CompositionSpecItem(BaseModel):
    """A single item in a composition specification.

    Parameters
    ----------
    content_hash : str
        SHA-256 hex digest of the content blob to include.
    weight : float
        Sampling weight for this entry in the composition.
    """

    content_hash: str
    weight: float


class FreezeVersionBody(BaseModel):
    """Request body for freezing a new corpus version.

    Parameters
    ----------
    note : str | None, optional
        Optional version note. Defaults to ``None``.
    label : str | None, optional
        Optional human-readable label. Defaults to ``None``.
    composition : list[CompositionSpecItem] | None, optional
        Optional composition specification for creating a virtual
        composition version. When present, creates a weighted
        composition instead of a HEAD snapshot. Defaults to ``None``.
    """

    note: str | None = None
    label: str | None = None
    composition: list[CompositionSpecItem] | None = None


class TagBody(BaseModel):
    """Request body for tagging a version (FR-023).

    Parameters
    ----------
    name : str
        Tag name (e.g. ``"v1.0"``, ``"baseline"``).
    """

    name: str


class LockBody(BaseModel):
    """Request body for acquiring a content lock.

    Parameters
    ----------
    scope : str
        Lock scope identifier (e.g. ``"corpus:42"``).
    holder : str
        Lock holder identifier.
    """

    scope: str
    holder: str


class LockOut(BaseModel):
    """Lock as returned by the API.

    Parameters
    ----------
    id : int
        Primary key.
    scope : str
        Lock scope identifier.
    holder : str
        Lock holder identifier.
    state : str
        Lock state (``"held"`` or ``"released"``).
    acquired_at : datetime
        Timestamp when the lock was acquired.
    released_at : datetime | None, optional
        Timestamp when the lock was released.
    """

    id: int
    scope: str
    holder: str
    state: str
    acquired_at: datetime
    released_at: datetime | None = None


class RevertBody(BaseModel):
    """Request body for reverting a corpus to a prior version.

    Parameters
    ----------
    to_version_id : int
        Primary key of the version to revert to.
    """

    to_version_id: int


class ImportStart(BaseModel):
    """Request body for starting a declarative content import job.

    Parameters
    ----------
    corpus_id : int
        Primary key of the target corpus.
    source : str
        Source slug identifying the content origin.
    config : dict
        Job-specific configuration parameters.
    """

    corpus_id: int
    source: str
    config: dict[str, Any]


class ImportJobOut(BaseModel):
    """Import job as returned by the API.

    Parameters
    ----------
    id : int
        Primary key.
    corpus_id : int
        FK to the target corpus.
    source_id : int
        FK to the content source.
    config_json : str
        JSON-serialised job configuration.
    status : str
        Current job status from ``IngestStatus``.
    session_id : int | None, optional
        FK to the linked ingest session, if any.
    message : str | None, optional
        Optional status or error message.
    started_at : datetime
        Timestamp when the job was started.
    finished_at : datetime | None, optional
        Timestamp when the job finished.
    """

    id: int
    corpus_id: int
    source_id: int
    config_json: str
    status: str
    session_id: int | None = None
    message: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
