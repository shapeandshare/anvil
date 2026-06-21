# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for GovernanceService, GateDecision, and ProvenanceView.

Tests the acceptable-use gate (all rejection and acceptance paths),
license catalog seeding (idempotency), provenance assignment and
lookup, and bundled-sample validation.
"""

from __future__ import annotations

import pytest

from anvil.db.repositories.audit_events import AuditEventRepository
from anvil.db.repositories.licenses import LicenseRepository
from anvil.services.governance.audit_service import AuditService
from anvil.services.governance.data_origin import DataOrigin
from anvil.services.governance.gate_decision import GateDecision
from anvil.services.governance.governance_service import GovernanceService
from anvil.services.governance.provenance_view import ProvenanceView

# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
async def gov_svc(in_memory_session):
    """Build a GovernanceService backed by an in-memory DB.

    Seeds the license catalog so that approval-path tests have
    entries to resolve against.
    """
    lic_repo = LicenseRepository(in_memory_session)
    audit_repo = AuditEventRepository(in_memory_session)
    audit = AuditService(audit_repo)
    svc = GovernanceService(lic_repo, audit)
    await svc.seed_catalog()
    return svc


# ═══════════════════════════════════════════════════════════════════
# GateDecision model
# ═══════════════════════════════════════════════════════════════════


class TestGateDecision:
    """GateDecision field defaults and construction."""

    def test_rejected_defaults(self):
        """A rejected decision has accepted=False and no license_id or
        origin."""
        d = GateDecision(accepted=False, reason="nope")
        assert d.accepted is False
        assert d.reason == "nope"
        assert d.license_id is None
        assert d.origin == DataOrigin.USER

    def test_accepted_all_fields(self):
        """An accepted decision carries the resolved license_id and
        origin."""
        d = GateDecision(
            accepted=True,
            license_id=5,
            origin=DataOrigin.BUNDLED,
        )
        assert d.accepted is True
        assert d.license_id == 5
        assert d.origin == DataOrigin.BUNDLED


# ═══════════════════════════════════════════════════════════════════
# ProvenanceView model
# ═══════════════════════════════════════════════════════════════════


class TestProvenanceView:
    """ProvenanceView field defaults and construction."""

    def test_defaults(self):
        """A default ProvenanceView has None for all optional fields."""
        v = ProvenanceView()
        assert v.source_description is None
        assert v.license is None
        assert v.attribution is None
        assert v.origin == DataOrigin.USER

    def test_all_fields(self):
        """All fields can be populated on construction."""
        v = ProvenanceView(
            source_description="test source",
            license="MIT",
            attribution="(c) Author",
            origin=DataOrigin.BUNDLED,
        )
        assert v.source_description == "test source"
        assert v.license == "MIT"
        assert v.attribution == "(c) Author"
        assert v.origin == DataOrigin.BUNDLED


# ═══════════════════════════════════════════════════════════════════
# GovernanceService — License catalog
# ═══════════════════════════════════════════════════════════════════


class TestListLicenses:
    """list_licenses filtering behaviour."""

    async def test_returns_all_by_default(self, gov_svc):
        """list_licenses without arguments returns all entries including
        the own-content sentinel."""
        licenses = await gov_svc.list_licenses()
        identifiers = {lic.identifier for lic in licenses}
        assert "MIT" in identifiers
        assert "own-content" in identifiers
        assert len(licenses) >= 9

    async def test_excludes_own_content(self, gov_svc):
        """list_licenses with include_own_content=False filters out the
        sentinel."""
        licenses = await gov_svc.list_licenses(include_own_content=False)
        identifiers = {lic.identifier for lic in licenses}
        assert "MIT" in identifiers
        assert "own-content" not in identifiers


class TestSeedCatalog:
    """seed_catalog idempotency."""

    async def test_seeds_initial_count(self, in_memory_session):
        """First call returns the number of newly inserted entries."""
        lic_repo = LicenseRepository(in_memory_session)
        audit_repo = AuditEventRepository(in_memory_session)
        audit = AuditService(audit_repo)
        svc = GovernanceService(lic_repo, audit)
        count = await svc.seed_catalog()
        assert count > 0

    async def test_seed_is_idempotent(self, gov_svc):
        """Second call returns 0 because all entries already exist."""
        count = await gov_svc.seed_catalog()
        assert count == 0


# ═══════════════════════════════════════════════════════════════════
# GovernanceService — Acceptable-use gate
# ═══════════════════════════════════════════════════════════════════


class TestEvaluateSubmission:
    """All rejection and acceptance paths for evaluate_submission."""

    async def test_rejects_empty_source(self, gov_svc):
        """Empty declared_source should be rejected."""
        result = await gov_svc.evaluate_submission(
            declared_source="",
            license_identifier="MIT",
            acceptable_use_affirmed=True,
            is_empty_or_unparseable=False,
            actor="test",
            target_type="dataset",
        )
        assert result.accepted is False
        assert "source description" in (result.reason or "").lower()

    async def test_rejects_empty_license(self, gov_svc):
        """Empty license_identifier should be rejected."""
        result = await gov_svc.evaluate_submission(
            declared_source="my data",
            license_identifier="",
            acceptable_use_affirmed=True,
            is_empty_or_unparseable=False,
            actor="test",
            target_type="dataset",
        )
        assert result.accepted is False
        assert "license" in (result.reason or "").lower()

    async def test_rejects_no_affirmation(self, gov_svc):
        """acceptable_use_affirmed=False should be rejected."""
        result = await gov_svc.evaluate_submission(
            declared_source="my data",
            license_identifier="MIT",
            acceptable_use_affirmed=False,
            is_empty_or_unparseable=False,
            actor="test",
            target_type="dataset",
        )
        assert result.accepted is False
        assert "affirm" in (result.reason or "").lower()

    async def test_rejects_empty_unparseable(self, gov_svc):
        """is_empty_or_unparseable=True should be rejected."""
        result = await gov_svc.evaluate_submission(
            declared_source="my data",
            license_identifier="MIT",
            acceptable_use_affirmed=True,
            is_empty_or_unparseable=True,
            actor="test",
            target_type="dataset",
        )
        assert result.accepted is False
        assert "empty" in (result.reason or "").lower()

    async def test_accepts_valid_license(self, gov_svc):
        """A valid submission with an approved license should be
        accepted and include the resolved license_id."""
        result = await gov_svc.evaluate_submission(
            declared_source="my data",
            license_identifier="MIT",
            acceptable_use_affirmed=True,
            is_empty_or_unparseable=False,
            actor="test",
            target_type="dataset",
        )
        assert result.accepted is True
        assert result.license_id is not None

    async def test_accepts_own_content(self, gov_svc):
        """Using the own-content sentinel should be accepted with no
        license_id."""
        result = await gov_svc.evaluate_submission(
            declared_source="my own data",
            license_identifier="own-content",
            acceptable_use_affirmed=True,
            is_empty_or_unparseable=False,
            actor="test",
            target_type="dataset",
        )
        assert result.accepted is True
        # own-content should still produce a license_id
        assert result.license_id is not None


# ═══════════════════════════════════════════════════════════════════
# GovernanceService — Provenance
# ═══════════════════════════════════════════════════════════════════


class TestAssignProvenance:
    """Provenance assignment to Dataset/Corpus entities."""

    async def test_assigns_to_dataset(self, tmp_path, in_memory_session, gov_svc):
        """Assigning provenance to a Dataset should set all provenance
        fields."""
        from anvil.db.models.dataset import Dataset

        ds = Dataset(
            name="test-ds", filename="test.txt", file_path=str(tmp_path / "ds.txt")
        )
        in_memory_session.add(ds)
        await in_memory_session.flush()
        await in_memory_session.refresh(ds)

        await gov_svc.assign_provenance(
            entity=ds,
            source_description="test source",
            license_id=1,
            attribution_text="(c) Author",
            origin=DataOrigin.USER,
        )
        assert ds.source_description == "test source"
        assert ds.license_id == 1
        assert ds.attribution_text == "(c) Author"
        assert ds.origin == "user"

    async def test_assigns_to_corpus(self, tmp_path, in_memory_session, gov_svc):
        """Assigning provenance to a Corpus should set all provenance
        fields."""
        from anvil.db.models.corpus import Corpus

        c = Corpus(
            name="test-corpus",
            root_path=str(tmp_path),
            chunking_strategy="line",
            chunk_overlap=0.0,
            file_count=0,
            document_count=0,
        )
        in_memory_session.add(c)
        await in_memory_session.flush()
        await in_memory_session.refresh(c)

        await gov_svc.assign_provenance(
            entity=c,
            source_description="corpus source",
            license_id=2,
            attribution_text="(c) Author",
            origin=DataOrigin.BUNDLED,
        )
        assert c.source_description == "corpus source"
        assert c.license_id == 2
        assert c.attribution_text == "(c) Author"
        assert c.origin == "bundled"

    async def test_raises_type_error_for_unsupported(self, gov_svc):
        """assign_provenance should raise TypeError for unsupported
        entity types."""
        with pytest.raises(TypeError, match="Unsupported entity type"):
            await gov_svc.assign_provenance(
                entity="not-a-model",
                source_description="test",
                license_id=1,
            )


class TestGetProvenance:
    """Provenance lookup for datasets and corpora."""

    async def test_returns_provenance_for_dataset(
        self, tmp_path, in_memory_session, gov_svc
    ):
        """get_provenance should return provenance data for a dataset."""
        from anvil.db.models.dataset import Dataset

        ds = Dataset(name="ds", filename="ds.txt", file_path=str(tmp_path / "ds.txt"))
        in_memory_session.add(ds)
        await in_memory_session.flush()
        await in_memory_session.refresh(ds)
        await gov_svc.assign_provenance(
            entity=ds,
            source_description="ds source",
            license_id=1,
            origin=DataOrigin.USER,
        )

        result = await gov_svc.get_provenance(target_type="dataset", target_id=ds.id)
        assert result.source_description == "ds source"
        assert result.origin == DataOrigin.USER

    async def test_returns_provenance_for_corpus(
        self, tmp_path, in_memory_session, gov_svc
    ):
        """get_provenance should return provenance data for a corpus."""
        from anvil.db.models.corpus import Corpus

        c = Corpus(
            name="corpus",
            root_path=str(tmp_path),
            chunking_strategy="line",
            chunk_overlap=0.0,
            file_count=0,
            document_count=0,
        )
        in_memory_session.add(c)
        await in_memory_session.flush()
        await in_memory_session.refresh(c)
        await gov_svc.assign_provenance(
            entity=c,
            source_description="corpus source",
            license_id=2,
            origin=DataOrigin.BUNDLED,
        )

        result = await gov_svc.get_provenance(target_type="corpus", target_id=c.id)
        assert result.source_description == "corpus source"
        assert result.origin == DataOrigin.BUNDLED

    async def test_returns_empty_for_nonexistent(self, gov_svc):
        """get_provenance for a non-existent entity should return a view
        with all defaults."""
        result = await gov_svc.get_provenance(target_type="dataset", target_id=9999)
        assert result.source_description is None
        assert result.origin == DataOrigin.USER


# ═══════════════════════════════════════════════════════════════════
# GovernanceService — Bundled validation
# ═══════════════════════════════════════════════════════════════════


class TestValidateBundled:
    """Bundled-sample provenance validation paths."""

    async def test_rejects_no_license(self, gov_svc):
        """validate_bundled with empty license returns False."""
        valid, _ = await gov_svc.validate_bundled(
            source_description="test", license_identifier=""
        )
        assert valid is False

    async def test_rejects_own_content(self, gov_svc):
        """validate_bundled with own-content sentinel returns False."""
        valid, _ = await gov_svc.validate_bundled(
            source_description="test", license_identifier="own-content"
        )
        assert valid is False

    async def test_rejects_unknown_license(self, gov_svc):
        """validate_bundled with an unapproved license returns False."""
        valid, _ = await gov_svc.validate_bundled(
            source_description="test", license_identifier="NONEXISTENT"
        )
        assert valid is False

    async def test_accepts_approved_license(self, gov_svc):
        """validate_bundled with an approved license returns True."""
        valid, _ = await gov_svc.validate_bundled(
            source_description="test", license_identifier="MIT"
        )
        assert valid is True
        assert _ is None
