# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for vault hygiene analysis (anvil/services/vault/hygiene.py)."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from unittest.mock import mock_open, patch

from anvil.services.vault._types import NoteMetadata
from anvil.services.vault.hygiene import (
    _classify_percentage,
    _find_near_duplicate_tags,
    _find_over_linking,
    _is_valid_date,
    _levenshtein_distance,
    _load_controlled_tags,
    compute_hygiene,
)


class TestClassifyPercentage:
    """Tests for _classify_percentage."""

    def test_healthy_at_100(self) -> None:
        assert _classify_percentage(100.0) == "healthy"

    def test_healthy_above_100(self) -> None:
        assert _classify_percentage(105.0) == "healthy"

    def test_warning_90_to_99(self) -> None:
        assert _classify_percentage(90.0) == "warning"
        assert _classify_percentage(95.0) == "warning"
        assert _classify_percentage(99.99) == "warning"

    def test_critical_below_90(self) -> None:
        assert _classify_percentage(89.0) == "critical"
        assert _classify_percentage(50.0) == "critical"
        assert _classify_percentage(0.0) == "critical"


class TestLevenshteinDistance:
    """Tests for _levenshtein_distance."""

    def test_identical_strings(self) -> None:
        assert _levenshtein_distance("hello", "hello") == 0

    def test_empty_strings(self) -> None:
        assert _levenshtein_distance("", "") == 0

    def test_one_empty(self) -> None:
        assert _levenshtein_distance("abc", "") == 3
        assert _levenshtein_distance("", "abc") == 3

    def test_single_substitution(self) -> None:
        assert _levenshtein_distance("cat", "car") == 1

    def test_single_insertion(self) -> None:
        assert _levenshtein_distance("cat", "cast") == 1

    def test_single_deletion(self) -> None:
        assert _levenshtein_distance("cast", "cat") == 1

    def test_completely_different(self) -> None:
        assert _levenshtein_distance("abc", "xyz") == 3


class TestIsValidDate:
    """Tests for _is_valid_date."""

    def test_none_is_invalid(self) -> None:
        assert _is_valid_date(None) is False

    def test_date_object(self) -> None:
        assert _is_valid_date(date(2024, 1, 15)) is True

    def test_datetime_object(self) -> None:
        assert _is_valid_date(datetime(2024, 1, 15, 10, 30, 0)) is True

    def test_iso_date_string(self) -> None:
        assert _is_valid_date("2024-01-15") is True

    def test_iso_datetime_string(self) -> None:
        assert _is_valid_date("2024-01-15T10:30:00") is True

    def test_iso_datetime_with_tz(self) -> None:
        assert _is_valid_date("2024-01-15T10:30:00Z") is True

    def test_iso_datetime_with_microseconds(self) -> None:
        assert _is_valid_date("2024-01-15T10:30:00.123456Z") is True

    def test_invalid_string(self) -> None:
        assert _is_valid_date("not-a-date") is False

    def test_partial_date(self) -> None:
        assert _is_valid_date("2024-13-01") is False

    def test_integer_is_invalid(self) -> None:
        assert _is_valid_date(20240115) is False

    def test_quoted_date_string(self) -> None:
        assert _is_valid_date("'2024-01-15'") is True


class TestFindNearDuplicateTags:
    """Tests for _find_near_duplicate_tags."""

    def test_no_duplicates(self) -> None:
        tags = ["alpha", "beta", "gamma"]
        assert _find_near_duplicate_tags(tags) == []

    def test_case_duplicate(self) -> None:
        tags = ["Alpha", "alpha"]
        result = _find_near_duplicate_tags(tags)
        assert len(result) == 1
        pair = result[0]
        assert "alpha" in pair
        assert "Alpha" in pair

    def test_levenshtein_near_duplicate(self) -> None:
        tags = ["sys/train", "sys/tain"]
        result = _find_near_duplicate_tags(tags)
        assert len(result) >= 1

    def test_levenshtein_distance_3_not_flagged(self) -> None:
        tags = ["abc", "abcdef"]
        result = _find_near_duplicate_tags(tags)
        assert len(result) == 0

    def test_empty_list(self) -> None:
        assert _find_near_duplicate_tags([]) == []


class TestLoadControlledTags:
    """Tests for _load_controlled_tags."""

    def test_loads_builtin_vocab_when_no_file(self, tmp_path: Path) -> None:
        vault_root = tmp_path / "docs" / "vault"
        vault_root.mkdir(parents=True)
        tags = _load_controlled_tags(vault_root)
        assert "type/principle" in tags
        assert "status/draft" in tags
        assert "domain/architecture" in tags

    def test_parses_list_items_from_tags_md(self, tmp_path: Path) -> None:
        vault_root = tmp_path / "docs" / "vault"
        vault_root.mkdir(parents=True)
        meta = vault_root / "_meta"
        meta.mkdir(parents=True)
        (meta / "tags.md").write_text(
            "---\nkey: val\n---\n- `domain/custom`\n- `status/experimental`\n"
        )
        tags = _load_controlled_tags(vault_root)
        assert "domain/custom" in tags
        assert "status/experimental" in tags
        assert "type/principle" in tags

    def test_skips_content_before_frontmatter_end(self, tmp_path: Path) -> None:
        vault_root = tmp_path / "docs" / "vault"
        vault_root.mkdir(parents=True)
        meta = vault_root / "_meta"
        meta.mkdir(parents=True)
        (meta / "tags.md").write_text("---\ntitle: Tags\n---\n- `domain/real`\n")
        tags = _load_controlled_tags(vault_root)
        assert "domain/real" in tags

    def test_handles_missing_file_gracefully(self, tmp_path: Path) -> None:
        vault_root = tmp_path / "docs" / "vault"
        vault_root.mkdir(parents=True)
        tags = _load_controlled_tags(vault_root)
        assert "type/principle" in tags


class TestFindOverLinking:
    """Tests for _find_over_linking."""

    def test_no_overlinking(self, tmp_path: Path) -> None:
        note_path = tmp_path / "note.md"
        note_path.write_text("---\ntitle: Test\n---\nContent [[target]] here.\n")
        meta = NoteMetadata(
            path=note_path, stem="note", tags=[], outbound_stems=["target"]
        )
        result = _find_over_linking({"note": meta}, tmp_path)
        assert result == []

    def test_duplicate_in_same_section(self, tmp_path: Path) -> None:
        note_path = tmp_path / "note.md"
        note_path.write_text(
            "---\ntitle: Test\n---\n[[target]] and [[target]] again.\n"
        )
        meta = NoteMetadata(
            path=note_path, stem="note", tags=[], outbound_stems=["target"]
        )
        result = _find_over_linking({"note": meta}, tmp_path)
        assert len(result) == 1
        assert result[0][0] == "note"

    def test_duplicates_in_different_sections_ok(self, tmp_path: Path) -> None:
        note_path = tmp_path / "note.md"
        note_path.write_text(
            "---\ntitle: Test\n---\n## Section A\n[[target]]\n## Section B\n[[target]]\n"
        )
        meta = NoteMetadata(
            path=note_path, stem="note", tags=[], outbound_stems=["target"]
        )
        result = _find_over_linking({"note": meta}, tmp_path)
        assert result == []

    def test_skips_unreadable_file(self, tmp_path: Path) -> None:
        meta = NoteMetadata(
            path=tmp_path / "nonexistent.md",
            stem="missing",
            tags=[],
            outbound_stems=[],
        )
        result = _find_over_linking({"missing": meta}, tmp_path)
        assert result == []


class TestComputeHygiene:
    """Tests for compute_hygiene."""

    def test_empty_notes(self, tmp_path: Path) -> None:
        result = compute_hygiene({}, tmp_path)
        assert result.tag_conformity_pct == 100.0
        assert result.frontmatter_completeness_pct == 100.0
        assert result.non_conformant_tags == []
        assert result.missing_fields == []
        assert result.phantom_links == []

    def test_conformant_note(self, tmp_path: Path) -> None:
        note = NoteMetadata(
            path=tmp_path / "test.md",
            stem="test",
            tags=["type/principle", "domain/core"],
            frontmatter={
                "title": "Test",
                "type": "principle",
                "tags": ["type/principle", "domain/core"],
                "created": "2024-01-01",
                "updated": "2024-06-01",
            },
        )
        result = compute_hygiene({"test": note}, tmp_path)
        assert result.tag_conformity_pct == 100.0
        assert result.frontmatter_completeness_pct == 100.0
        assert result.non_conformant_tags == []
        assert result.missing_fields == []

    def test_non_conformant_tag(self, tmp_path: Path) -> None:
        note = NoteMetadata(
            path=tmp_path / "test.md",
            stem="test",
            tags=["type/unknown"],
            frontmatter={
                "title": "Test",
                "type": "principle",
                "tags": ["type/unknown"],
                "created": "2024-01-01",
                "updated": "2024-06-01",
            },
        )
        result = compute_hygiene({"test": note}, tmp_path)
        assert result.non_conformant_tags == [("test", "type/unknown")]

    def test_missing_required_fields(self, tmp_path: Path) -> None:
        note = NoteMetadata(
            path=tmp_path / "test.md",
            stem="test",
            tags=[],
            frontmatter={"title": "Test"},
        )
        result = compute_hygiene({"test": note}, tmp_path)
        missing_fields = dict(result.missing_fields)
        missing_stems = {s for s, _ in result.missing_fields}
        assert "test" in missing_stems

    def test_type_mismatch_tags_not_list(self, tmp_path: Path) -> None:
        note = NoteMetadata(
            path=tmp_path / "test.md",
            stem="test",
            tags=[],
            frontmatter={
                "title": "Test",
                "type": "principle",
                "tags": "not-a-list",
                "created": "2024-01-01",
                "updated": "2024-06-01",
            },
        )
        result = compute_hygiene({"test": note}, tmp_path)
        assert ("test", "tags", "list") in result.type_mismatches

    def test_inconsistent_dates(self, tmp_path: Path) -> None:
        note = NoteMetadata(
            path=tmp_path / "test.md",
            stem="test",
            tags=[],
            frontmatter={
                "title": "Test",
                "type": "principle",
                "tags": [],
                "created": "bad-date",
                "updated": "2024-06-01",
            },
        )
        result = compute_hygiene({"test": note}, tmp_path)
        assert len(result.inconsistent_dates) == 1
        assert "bad-date" in result.inconsistent_dates[0][1]

    def test_phantom_links(self, tmp_path: Path) -> None:
        note = NoteMetadata(
            path=tmp_path / "test.md",
            stem="test",
            tags=[],
            outbound_stems=["nonexistent_note"],
            frontmatter={
                "title": "Test",
                "type": "principle",
                "tags": [],
                "created": "2024-01-01",
                "updated": "2024-06-01",
            },
        )
        result = compute_hygiene({"test": note}, tmp_path)
        assert ("test", "nonexistent_note") in result.phantom_links

    def test_resolved_phantom_link_with_path(self, tmp_path: Path) -> None:
        """Phantom link with path separator should resolve to stem."""
        note = NoteMetadata(
            path=tmp_path / "test.md",
            stem="test",
            tags=[],
            outbound_stems=["some_dir/target"],
            frontmatter={
                "title": "Test",
                "type": "principle",
                "tags": [],
                "created": "2024-01-01",
                "updated": "2024-06-01",
            },
        )
        result = compute_hygiene({"test": note}, tmp_path)
        assert ("test", "some_dir/target") in result.phantom_links

    def test_single_use_tags_detected(self, tmp_path: Path) -> None:
        note = NoteMetadata(
            path=tmp_path / "a.md",
            stem="a",
            tags=["type/principle", "domain/rare"],
            frontmatter={
                "title": "A",
                "type": "principle",
                "tags": ["type/principle", "domain/rare"],
                "created": "2024-01-01",
                "updated": "2024-06-01",
            },
        )
        result = compute_hygiene({"a": note}, tmp_path)
        assert "domain/rare" in result.single_use_tags