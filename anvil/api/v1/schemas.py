"""Request body models for v1 API endpoints.

Pure Pydantic ``BaseModel`` subclasses used as request bodies for
dataset management endpoints.  No business logic -- validation only.
"""

from datetime import datetime

from pydantic import BaseModel


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
