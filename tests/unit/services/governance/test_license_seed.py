"""Unit tests for the license catalog seed data.

Verifies that the seed set contains the correct broad OSI/CC set,
that the own-content sentinel is correctly flagged, and that
attribution-required licenses are marked as such.
"""

from __future__ import annotations

from anvil.services.governance.license_seed import SEED


def test_seed_contains_expected_entries():
    """The seed list should contain the expected broad OSI/CC set."""
    identifiers = [e._identifier for e in SEED]

    expected = [
        "Public Domain",
        "CC0-1.0",
        "MIT",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "Apache-2.0",
        "CC-BY-4.0",
        "CC-BY-SA-4.0",
        "Generated/Original",
        "own-content",
    ]
    for e in expected:
        assert e in identifiers, f"Missing expected license: {e}"


def test_own_content_sentinel():
    """The own-content entry should be flagged correctly."""
    own = [e for e in SEED if e._identifier == "own-content"]
    assert len(own) == 1, "Expected exactly one own-content sentinel"
    own_entry = own[0]
    assert own_entry._is_own_content_sentinel is True
    assert own_entry._redistribution_allowed is False


def test_attribution_required_licenses():
    """Licenses that require attribution should be flagged."""
    attrib_required = [e for e in SEED if e._requires_attribution]
    attrib_ids = {e._identifier for e in attrib_required}
    assert "CC-BY-4.0" in attrib_ids
    assert "CC-BY-SA-4.0" in attrib_ids


def test_attribution_not_required_by_default():
    """Most licenses should not require attribution."""
    attrib_not_required = [e for e in SEED if not e._requires_attribution and not e._is_own_content_sentinel]
    assert len(attrib_not_required) >= 6


def test_redistribution_allowed_by_default():
    """Most licenses should allow redistribution."""
    redist_allowed = [e for e in SEED if e._redistribution_allowed]
    assert len(redist_allowed) >= 8


def test_seed_to_model():
    """Each seed entry should produce a valid LicenseEntry model."""
    for entry in SEED:
        model = entry.to_model()
        assert model.identifier == entry._identifier
        assert model.display_name == entry._display_name
        assert model.requires_attribution == entry._requires_attribution
        assert model.redistribution_allowed == entry._redistribution_allowed
        assert model.is_own_content_sentinel == entry._is_own_content_sentinel