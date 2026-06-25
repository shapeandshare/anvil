# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Governance service — acceptable-use gate, license catalog & provenance.

Implements the data-entry gate (declaration/affirmation-only, no
content scanning), the approved-license catalog, and provenance
assignment/lookup.  Exposed through the ``AnvilWorkbench`` God Class
as ``workbench.governance``.
"""

from __future__ import annotations

from collections.abc import Sequence

from ...db.models.license_entry import LicenseEntry
from ...db.repositories.licenses import LicenseRepository
from .audit_action import AuditAction
from .audit_outcome import AuditOutcome
from .audit_service import AuditService
from .audit_target_type import AuditTargetType
from .data_origin import DataOrigin
from .gate_decision import GateDecision
from .license_seed import SEED
from .provenance_view import ProvenanceView


class GovernanceService:
    """Highest-level governance facade.

    Parameters
    ----------
    license_repo : LicenseRepository
        Repository for the approved-license catalog.
    audit : AuditService
        The hash-chained audit trail service.
    """

    def __init__(
        self,
        license_repo: LicenseRepository,
        audit: AuditService,
    ) -> None:
        self._license_repo = license_repo
        self._audit = audit

    # ── License catalog ─────────────────────────────────────────────────

    async def list_licenses(
        self, *, include_own_content: bool = True
    ) -> Sequence[LicenseEntry]:
        """Return all approved licenses."""
        licenses = await self._license_repo.all()
        if not include_own_content:
            licenses = [lic for lic in licenses if not lic.is_own_content_sentinel]
        return licenses

    async def seed_catalog(self) -> int:
        """Idempotently seed the license catalog from the seed list.

        Skips identifiers that already exist.  Returns the number of
        newly inserted entries.
        """
        count = 0
        for entry in SEED:
            existing = await self._license_repo.get_by_identifier(entry._identifier)
            if existing is None:
                await self._license_repo.add(entry.to_model())
                count += 1
        return count

    # ── Acceptable-use gate ─────────────────────────────────────────────

    async def evaluate_submission(
        self,
        *,
        declared_source: str,
        license_identifier: str,
        acceptable_use_affirmed: bool,
        is_empty_or_unparseable: bool,
        actor: str,
        target_type: str,
        target_id: str | None = None,
    ) -> GateDecision:
        """Evaluate a data submission against the acceptable-use gate.

        Declaration/affirmation-only — performs **no** content
        scanning (Clarification Q3).  Records every decision as a
        ``POLICY_ACCEPT`` or ``POLICY_REJECT`` audit event (FR-016).

        Returns
        -------
        GateDecision
            ``accepted=True`` with a resolved ``license_id`` for
            compliant submissions; ``accepted=False`` with a clear
            ``reason`` for rejections.
        """
        # ── Validation ──────────────────────────────────────────────────
        reject_reason: str | None = None

        if not declared_source:
            reject_reason = "A source description is required."

        elif not license_identifier:
            reject_reason = "A license declaration is required."

        elif not acceptable_use_affirmed:
            reject_reason = (
                "You must affirm that your submission complies "
                "with the universal no-harm acceptable-use policy."
            )

        elif is_empty_or_unparseable:
            reject_reason = (
                "The submitted content is empty or could not be "
                "parsed.  Please check your file and try again."
            )

        if reject_reason is not None:
            await self._audit.record(
                action_type=AuditAction.POLICY_REJECT.value,
                target_type=target_type,
                target_id=target_id,
                actor=actor,
                outcome=AuditOutcome.REJECTED.value,
                reason=reject_reason,
                params={
                    "declared_source": declared_source,
                    "license": license_identifier,
                },
            )
            return GateDecision(accepted=False, reason=reject_reason)

        # ── Resolve license ──────────────────────────────────────────────
        license_id: int | None = None
        origin = DataOrigin.USER

        if license_identifier == "own-content":
            own = await self._license_repo.get_by_identifier("own-content")
            if own is not None:
                license_id = own.id
        else:
            resolved = await self._license_repo.get_by_identifier(license_identifier)
            if resolved is not None:
                license_id = resolved.id
                origin = DataOrigin.USER

        await self._audit.record(
            action_type=AuditAction.POLICY_ACCEPT.value,
            target_type=target_type,
            target_id=target_id,
            actor=actor,
            outcome=AuditOutcome.SUCCESS.value,
            params={
                "declared_source": declared_source,
                "license": license_identifier,
                "license_id": license_id,
            },
        )
        return GateDecision(
            accepted=True,
            license_id=license_id,
            origin=origin,
        )

    # ── Provenance ──────────────────────────────────────────────────────

    async def assign_provenance(
        self,
        *,
        entity: object,
        source_description: str,
        license_id: int,
        attribution_text: str | None = None,
        origin: DataOrigin = DataOrigin.USER,
        parent_provenance_ref: int | None = None,
    ) -> None:
        """Assign provenance fields to a dataset or corpus.

        Parameters
        ----------
        entity : Dataset | Corpus
            The ORM instance to update.
        source_description : str
            Where the data came from.
        license_id : int
            Foreign key into ``license_catalog``.
        attribution_text : str, optional
            Required attribution (must be non-empty when the license
            ``requires_attribution`` — caller validates via
            :meth:`validate_attribution`).
        origin : DataOrigin
            ``bundled`` or ``user``.
        parent_provenance_ref : int, optional
            Parent dataset/corpus id when this data is derived.
        """
        # Import here to avoid circular type dependency.
        from ...db.models.corpus import Corpus
        from ...db.models.dataset import Dataset

        if isinstance(entity, Dataset):
            entity.source_description = source_description
            entity.license_id = license_id
            entity.attribution_text = attribution_text
            entity.origin = origin.value
            entity.parent_provenance_ref = parent_provenance_ref
        elif isinstance(entity, Corpus):
            entity.source_description = source_description
            entity.license_id = license_id
            entity.attribution_text = attribution_text
            entity.origin = origin.value
            entity.parent_provenance_ref = parent_provenance_ref
        else:
            raise TypeError(f"Unsupported entity type: {type(entity)}")

    async def get_provenance(
        self,
        *,
        target_type: str,
        target_id: int,
    ) -> ProvenanceView:
        """Return the provenance record for a dataset or corpus.

        Parameters
        ----------
        target_type : str
            ``"dataset"`` or ``"corpus"``.
        target_id : int
            The entity's primary key.

        Returns
        -------
        ProvenanceView
            The provenance data, or a view with all fields ``None``
            if the entity is not found or has no provenance.
        """
        from ...db.models.corpus import Corpus
        from ...db.models.dataset import Dataset

        entity: Dataset | Corpus | None = None

        from ...db.repositories.corpora import CorpusRepository
        from ...db.repositories.datasets import DatasetRepository

        # TODO: wire through workbench.dataset_repo once provenance
        # methods on the repo are added (T030).  For now construct
        # inline — will be migrated at that point.
        repo: DatasetRepository | CorpusRepository
        if target_type == AuditTargetType.DATASET.value:
            repo = DatasetRepository(self._audit._repo._session)
            entity = await repo.get(target_id)

        elif target_type == AuditTargetType.CORPUS.value:
            repo = CorpusRepository(self._audit._repo._session)
            entity = await repo.get(target_id)

        if entity is None:
            return ProvenanceView(origin=DataOrigin.USER)

        license_identifier: str | None = None
        if entity.license_id is not None:
            lic = await self._license_repo.get(entity.license_id)
            if lic is not None:
                license_identifier = lic.identifier

        return ProvenanceView(
            source_description=entity.source_description,
            license=license_identifier,
            attribution=entity.attribution_text,
            origin=DataOrigin(entity.origin) if entity.origin else DataOrigin.USER,
        )

    async def validate_bundled(
        self,
        *,
        _source_description: str,
        license_identifier: str,
    ) -> tuple[bool, str | None]:
        """Validate a bundled sample's provenance (VR-P1).

        Returns ``(True, None)`` when the license is approved and
        known; ``(False, reason)`` otherwise.
        """
        if not license_identifier:
            return False, "No license declared."

        if license_identifier == "own-content":
            return False, "Bundled data may not use the own-content sentinel."

        entry = await self._license_repo.get_by_identifier(license_identifier)
        if entry is None:
            return (
                False,
                f"License '{license_identifier}' is not in the approved catalog.",
            )

        return True, None
