# Copyright © 2026 Josh Burt
# one-class:allow — intentional domain grouping of tightly coupled governance schemas
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Request/response models for governance API endpoints.

Pure Pydantic ``BaseModel`` subclasses used for governance-related
endpoints including audit, provenance, takedown, and upload gates.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


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
