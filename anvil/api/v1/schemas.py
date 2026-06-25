# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Request body models for v1 API endpoints.

Pure Pydantic ``BaseModel`` subclasses used as request bodies for
dataset management endpoints.  No business logic -- validation only.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CreateDatasetBody(BaseModel):
    """Request body for creating a new dataset.

    Parameters
    ----------
    name : str
        The dataset name.
    description : str | None, optional
        Optional description. Defaults to ``None``.
    """

    name: str
    description: str | None = None


class UpdateDatasetBody(BaseModel):
    """Request body for updating an existing dataset.

    Parameters
    ----------
    name : str | None, optional
        New dataset name. Defaults to ``None``.
    description : str | None, optional
        New description. Defaults to ``None``.
    """

    name: str | None = None
    description: str | None = None


class ImportBody(BaseModel):
    """Request body for importing text into a dataset.

    Parameters
    ----------
    format : str
        Import format (e.g. ``"txt"``, ``"csv"``, ``"jsonl"``).
    text : str
        Raw text content to import.
    """

    format: str
    text: str


class FilterBody(BaseModel):
    """Request body for filtering dataset samples by length.

    Parameters
    ----------
    min_length : int | None, optional
        Minimum sample length in characters. Defaults to ``None``.
    max_length : int | None, optional
        Maximum sample length in characters. Defaults to ``None``.
    """

    min_length: int | None = None
    max_length: int | None = None


class ReplaceBody(BaseModel):
    """Request body for regex replacement across dataset samples.

    Parameters
    ----------
    pattern : str
        Regex pattern to match.
    replacement : str
        Replacement string.
    case_sensitive : bool, optional
        Whether the regex is case-sensitive. Defaults to ``True``.
    """

    pattern: str
    replacement: str
    case_sensitive: bool = True


class UpdateSampleBody(BaseModel):
    """Request body for updating a single dataset sample.

    Parameters
    ----------
    text : str
        New text content for the sample.
    """

    text: str


class CloneDatasetBody(BaseModel):
    """Request body for cloning an existing dataset.

    Parameters
    ----------
    name : str
        Name for the new cloned dataset.
    description : str | None, optional
        Optional description. Defaults to ``None``.
    """

    name: str
    description: str | None = None


class CreateFromCorpusBody(BaseModel):
    """Request body for creating a dataset from a corpus with chunking.

    Parameters
    ----------
    corpus_id : int
        The source corpus ID.
    name : str
        Name for the new dataset.
    description : str | None, optional
        Optional description. Defaults to ``None``.
    chunking_strategy : str, optional
        Chunking strategy (``"windowed"``, ``"file"``, or ``"line"``).
        Defaults to ``"windowed"``.
    block_size : int | None, optional
        Block size for windowed chunking. Required when strategy is
        ``"windowed"``. Defaults to ``None``.
    chunk_overlap : float, optional
        Overlap fraction for windowed chunking. Defaults to ``0.25``.
    """

    corpus_id: int
    name: str
    description: str | None = None
    chunking_strategy: str = "windowed"
    block_size: int | None = None
    chunk_overlap: float = 0.25


class AuditEventOut(BaseModel):
    """Audit trail event as returned by governance API endpoints.

    Parameters
    ----------
    id : int
        The audit event's primary key.
    sequence : int
        Monotonic chain ordinal. Genesis entry has ``sequence=1``.
    action_type : str
        Discriminator from ``AuditAction`` StrEnum.
    target_type : str
        Discriminator from ``AuditTargetType`` StrEnum.
    target_id : str | None
        Loose string reference to the target entity.
    actor : str
        Operating user/session or automated process name.
    outcome : str
        Discriminator from ``AuditOutcome`` StrEnum.
    reason : str | None, optional
        Human-readable explanation (esp. for rejections).
    event_timestamp : datetime
        The action's timestamp.
    """

    id: int
    sequence: int
    action_type: str
    target_type: str
    target_id: str | None = None
    actor: str
    outcome: str
    reason: str | None = None
    event_timestamp: datetime


class ChainVerifyOut(BaseModel):
    """Outcome of an audit-chain integrity check.

    Parameters
    ----------
    valid : bool
        ``True`` when the entire chain is intact.
    break_at_sequence : int | None, optional
        The first ``sequence`` where a break was detected, or ``None``
        when *valid* is ``True``.
    entries_checked : int
        Number of entries verified.
    """

    valid: bool
    break_at_sequence: int | None = None
    entries_checked: int = 0


class ProvenanceOut(BaseModel):
    """Human-readable provenance metadata for a dataset or corpus.

    Parameters
    ----------
    source_description : str | None, optional
        Where the data came from (e.g. ``"Project Gutenberg #11"``).
    license : str | None, optional
        The license identifier from the approved catalog.
    attribution : str | None, optional
        Required attribution text.
    origin : str
        ``"bundled"`` (ships with the app) or ``"user"`` (supplied by user).
    """

    source_description: str | None = None
    license: str | None = None
    attribution: str | None = None
    origin: str = "user"


class DatasetGovernanceReportOut(BaseModel):
    """Combined provenance and audit report for a dataset.

    Parameters
    ----------
    provenance : ProvenanceOut
        The dataset's provenance metadata.
    audit : list[AuditEventOut]
        Chronological list of audit events for this dataset.
    """

    provenance: ProvenanceOut
    audit: list[AuditEventOut]


class TakedownBody(BaseModel):
    """Request body for a takedown request.

    Parameters
    ----------
    reason : str
        Human-readable explanation for the takedown request.
    """

    reason: str


class UploadGateFields(BaseModel):
    """Declaration/affirmation fields for the acceptable-use upload gate.

    Parameters
    ----------
    declared_source : str
        Where the data came from (user-supplied description).
    license : str
        The license identifier from the approved catalog.
    acceptable_use_affirmed : bool
        Whether the user affirms compliance with the no-harm policy.
    """

    declared_source: str
    license: str
    acceptable_use_affirmed: bool


# ── Content Repository (US1) schemas ────────────────────────────────────


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


# ── Content Import (US6) schemas ──────────────────────────────────────


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


# ── Corpus Management (T006) schemas ──────────────────────────────────


class CreateCorpusBody(BaseModel):
    """Request body for creating a new corpus from a directory path.

    Parameters
    ----------
    name : str
        The corpus name. Must be 1-255 characters.
    root_path : str
        Filesystem path to scan. Must be 1-255 characters.
    include_patterns : list[str] | None, optional
        Gitignore-style include patterns. Defaults to ``None``.
    exclude_patterns : list[str] | None, optional
        Gitignore-style exclude patterns. Defaults to ``None``.
    description : str | None, optional
        Optional description. Defaults to ``None``.
    chunking_strategy : str, optional
        Chunking algorithm (``"windowed"``, ``"file"``, or ``"line"``).
        Defaults to ``"windowed"``.
    chunk_overlap : float, optional
        Fractional overlap between chunks. Defaults to ``0.5``.
    block_size : int, optional
        Token block size for windowed chunking. Defaults to ``16``.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    root_path: str = Field(min_length=1, max_length=255)
    include_patterns: list[str] | None = None
    exclude_patterns: list[str] | None = None
    description: str | None = None
    chunking_strategy: str = "windowed"
    chunk_overlap: float = 0.5
    block_size: int = 16


class ForkCorpusBody(BaseModel):
    """Request body for forking an existing corpus.

    Parameters
    ----------
    name : str
        New corpus name. Must be 1-255 characters.
    include_patterns : list[str] | None, optional
        Gitignore-style include patterns. Defaults to ``None``.
    exclude_patterns : list[str] | None, optional
        Gitignore-style exclude patterns. Defaults to ``None``.
    description : str | None, optional
        Optional description. Defaults to ``None``.
    chunking_strategy : str | None, optional
        Chunking strategy override. Defaults to ``None``.
    chunk_overlap : float | None, optional
        Overlap override. Defaults to ``None``.
    block_size : int | None, optional
        Block size override. Defaults to ``None``.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    include_patterns: list[str] | None = None
    exclude_patterns: list[str] | None = None
    description: str | None = None
    chunking_strategy: str | None = None
    chunk_overlap: float | None = None
    block_size: int | None = None


class ResolvePathBody(BaseModel):
    """Request body for resolving a folder name to an absolute path.

    Parameters
    ----------
    folder_name : str
        The folder name to locate. Must be 1-255 characters.
    """

    model_config = ConfigDict(extra="forbid")

    folder_name: str = Field(min_length=1, max_length=255)


class AnalyzePathBody(BaseModel):
    """Request body for analyzing a directory path.

    Parameters
    ----------
    path : str
        Directory path to analyze. Must be 1-255 characters.
    include_patterns : list[str] | None, optional
        Gitignore-style include patterns. Defaults to ``None``.
    exclude_patterns : list[str] | None, optional
        Gitignore-style exclude patterns. Defaults to ``None``.
    """

    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1, max_length=255)
    include_patterns: list[str] | None = None
    exclude_patterns: list[str] | None = None


# ── Model Registry (T006/T008) schemas ────────────────────────────────


class RegisterModelBody(BaseModel):
    """Request body for registering a trained model from an experiment.

    Parameters
    ----------
    experiment_id : int
        The experiment ID to register the model from.
    """

    model_config = ConfigDict(extra="forbid")

    experiment_id: int


# ── Eval schemas (T006/T008) ──────────────────────────────────────────


class EvalPerplexityBody(BaseModel):
    """Request body for computing perplexity on a text.

    Parameters
    ----------
    model_id : int
        Identifier of the model.
    version : int
        Version of the model.
    text : str
        Input text to evaluate. Must be non-empty.
    """

    model_config = ConfigDict(extra="forbid")

    model_id: int
    version: int
    text: str = Field(min_length=1)


class CreateEvalDatasetBody(BaseModel):
    """Request body for creating a new evaluation dataset.

    Parameters
    ----------
    name : str
        The dataset name. Must be 1-255 characters.
    tags : dict | None, optional
        Optional metadata tags. Defaults to ``None``.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    tags: dict[str, Any] | None = None


class AppendRecordsBody(BaseModel):
    """Request body for appending records to an evaluation dataset.

    Parameters
    ----------
    records : list
        List of evaluation records to append.
    """

    model_config = ConfigDict(extra="forbid")

    records: list[Any]


# ── Inference schemas (T006/T008) ─────────────────────────────────────


class InferenceSampleBody(BaseModel):
    """Request body for generating text samples from a registered model.

    Parameters
    ----------
    model_id : int
        Identifier of the model.
    version : int
        Version of the model.
    temperature : float, optional
        Sampling temperature. Defaults to ``0.5``.
    num_samples : int, optional
        Number of samples to generate. Defaults to ``10``.
    prompt : str, optional
        Optional prompt text. Defaults to ``""``.
    top_k : int | None, optional
        Top-K sampling parameter. Defaults to ``None``.
    top_p : float | None, optional
        Top-P (nucleus) sampling parameter. Defaults to ``None``.
    """

    model_config = ConfigDict(extra="forbid")

    model_id: int
    version: int
    temperature: float = 0.5
    num_samples: int = 10
    prompt: str = ""
    top_k: int | None = None
    top_p: float | None = None


# ── Dataset Import schemas (T006/T008) ────────────────────────────────


class ImportFromCorpusBody(BaseModel):
    """Request body for importing documents from a corpus into a dataset.

    Parameters
    ----------
    corpus_id : int
        The source corpus ID.
    """

    model_config = ConfigDict(extra="forbid")

    corpus_id: int


# ── Content Source schemas (T006/T008) ────────────────────────────────


class CreateSourceBody(BaseModel):
    """Request body for creating a new content source.

    Parameters
    ----------
    slug : str
        Unique machine-readable identifier. Must be 1-255 characters.
    name : str
        Human-readable name. Must be 1-255 characters.
    kind : str, optional
        Source kind (e.g. ``"manual"``). Defaults to ``"manual"``.
    """

    model_config = ConfigDict(extra="forbid")

    slug: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=255)
    kind: str = "manual"
