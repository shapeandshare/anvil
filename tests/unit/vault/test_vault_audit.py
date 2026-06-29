# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for the vault mechanical audit service.

Tests ``VaultAuditService`` and its helper functions:
``_is_scaffold_path``, ``_is_spec_subfile``, ``nfc``,
``_nfc_strings``, ``parse_frontmatter``, ``extract_wikilinks``,
``_resolve_note_type``, ``_parse_date_value``, and
``validate_schema``.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from anvil.services.vault.types_finding import Finding
from anvil.services.vault.types_mechanical_report import MechanicalReport
from anvil.services.vault.vault_audit import (
    AGENT_NOTE_TYPES,
    DOMAIN_VOCAB,
    GROUNDED_NOTE_TYPES,
    KNOWN_TAG_PREFIXES,
    REQUIRED_FIELDS,
    SCAFFOLD_SUBDIRS,
    STATUS_VOCAB,
    TYPE_VOCAB,
    VaultAuditService,
    _is_scaffold_path,
    _is_spec_subfile,
    _nfc_strings,
    _parse_date_value,
    _resolve_note_type,
    extract_wikilinks,
    nfc,
    parse_frontmatter,
    validate_schema,
)

########################################################################
# Pure function tests
########################################################################


class TestNfc:
    """Tests for NFC Unicode normalization."""

    def test_already_nfc(self) -> None:
        """Normal ASCII strings pass through unchanged."""
        assert nfc("hello") == "hello"

    def test_nfd_to_nfc(self) -> None:
        """NFD-encoded characters are converted to NFC."""
        # e-acute in NFD (e + combining acute) vs NFC (é)
        cafe_nfd = "cafe\u0301"
        cafe_nfc = "caf\u00e9"
        assert nfc(cafe_nfd) == cafe_nfc


class TestNfcStrings:
    """Tests for recursive NFC normalization."""

    def test_normalizes_strings(self) -> None:
        """Plain strings are normalized."""
        result = _nfc_strings("cafe\u0301")
        assert result == "caf\u00e9"

    def test_normalizes_dict_values_recursively(self) -> None:
        """Dict values are recursively normalized; keys pass through unchanged."""
        data = {"cafe\u0301": "resume\u0301", "name": "hello"}
        result = _nfc_strings(data)
        # Keys are NOT normalized by _nfc_strings
        assert result.get("cafe\u0301") == "resum\u00e9"
        assert result["name"] == "hello"

    def test_normalizes_list_items(self) -> None:
        """List items are recursively normalized."""
        result = _nfc_strings(["cafe\u0301", "hello"])
        assert result == ["caf\u00e9", "hello"]

    def test_passes_non_string_types(self) -> None:
        """Non-string types (int, None) pass through unchanged."""
        result = _nfc_strings({"count": 42, "active": None})
        assert result == {"count": 42, "active": None}


class TestIsScaffoldPath:
    """Tests for _is_scaffold_path detection."""

    def test_scaffold_checklist(self, tmp_path: Path) -> None:
        """A path under Specs/*/checklists/ is scaffold."""
        vault_root = tmp_path / "docs" / "vault"
        file_path = vault_root / "Specs" / "001 Design" / "checklists" / "items.md"
        assert _is_scaffold_path(file_path, vault_root) is True

    def test_scaffold_contract(self, tmp_path: Path) -> None:
        """A path under Specs/*/contracts/ is scaffold."""
        vault_root = tmp_path / "docs" / "vault"
        file_path = vault_root / "Specs" / "001 Design" / "contracts" / "agreement.md"
        assert _is_scaffold_path(file_path, vault_root) is True

    def test_not_scaffold_root_note(self, tmp_path: Path) -> None:
        """The root Specs/*/ note is not scaffold."""
        vault_root = tmp_path / "docs" / "vault"
        file_path = vault_root / "Specs" / "001 Design.md"
        assert _is_scaffold_path(file_path, vault_root) is False

    def test_not_scaffold_spec_subfile(self, tmp_path: Path) -> None:
        """A spec subfile (Specs/*/NNN Title - tasks.md) is not scaffold."""
        vault_root = tmp_path / "docs" / "vault"
        file_path = vault_root / "Specs" / "001 Design" / "001 Design - tasks.md"
        assert _is_scaffold_path(file_path, vault_root) is False

    def test_not_scaffold_outside_vault(self, tmp_path: Path) -> None:
        """A path outside vault_root is not scaffold."""
        vault_root = tmp_path / "docs" / "vault"
        file_path = tmp_path / "other" / "file.md"
        assert _is_scaffold_path(file_path, vault_root) is False

    def test_not_scaffold_no_specs_dir(self, tmp_path: Path) -> None:
        """A path with no Specs/ in its relative path is not scaffold."""
        vault_root = tmp_path / "docs" / "vault"
        file_path = vault_root / "some-note.md"
        assert _is_scaffold_path(file_path, vault_root) is False

    def test_scaffold_shallow_path_not_scaffold(self, tmp_path: Path) -> None:
        """Specs/*/<scaffold> without a file beneath is not scaffold
        (need 4 parts: Specs / <dir> / <scaffold> / <file>).
        """
        vault_root = tmp_path / "docs" / "vault"
        file_path = vault_root / "Specs" / "001 Design" / "checklists"
        # This is a directory, not a file — but treated as path
        assert _is_scaffold_path(file_path, vault_root) is False

    def test_custom_scaffold_subdirs(self, tmp_path: Path) -> None:
        """Custom scaffold_subdirs overrides the default set."""
        vault_root = tmp_path / "docs" / "vault"
        file_path = vault_root / "Specs" / "001" / "templates" / "doc.md"
        assert (
            _is_scaffold_path(file_path, vault_root, scaffold_subdirs={"templates"})
            is True
        )


class TestIsSpecSubfile:
    """Tests for _is_spec_subfile detection."""

    def test_is_spec_subfile(self, tmp_path: Path) -> None:
        """A file under Specs/NNN Title/ not matching the dir name is a subfile."""
        vault_root = tmp_path / "docs" / "vault"
        file_path = vault_root / "Specs" / "001 Design" / "001 Design - plan.md"
        assert _is_spec_subfile(file_path, vault_root) is True

    def test_root_note_not_subfile(self, tmp_path: Path) -> None:
        """The root note (matching dir name) is not a subfile."""
        vault_root = tmp_path / "docs" / "vault"
        file_path = vault_root / "Specs" / "001 Design" / "001 Design.md"
        assert _is_spec_subfile(file_path, vault_root) is False

    def test_scaffold_not_subfile(self, tmp_path: Path) -> None:
        """A file under a scaffold subdir is not a spec subfile."""
        vault_root = tmp_path / "docs" / "vault"
        file_path = (
            vault_root / "Specs" / "001 Design" / "checklists" / "requirements.md"
        )
        assert _is_spec_subfile(file_path, vault_root) is False

    def test_outside_vault_not_subfile(self, tmp_path: Path) -> None:
        """A path outside vault_root is not a spec subfile."""
        vault_root = tmp_path / "docs" / "vault"
        file_path = tmp_path / "other" / "file.md"
        assert _is_spec_subfile(file_path, vault_root) is False

    def test_no_specs_dir_not_subfile(self, tmp_path: Path) -> None:
        """A path without Specs/ in its relative path is not a subfile."""
        vault_root = tmp_path / "docs" / "vault"
        file_path = vault_root / "some-note.md"
        assert _is_spec_subfile(file_path, vault_root) is False

    def test_short_path_not_subfile(self, tmp_path: Path) -> None:
        """Specs/<dir> only (no file) is not a subfile."""
        vault_root = tmp_path / "docs" / "vault"
        file_path = vault_root / "Specs" / "001 Design"
        assert _is_spec_subfile(file_path, vault_root) is False

    def test_scaffold_nested_not_subfile(self, tmp_path: Path) -> None:
        """A path inside a scaffold subdir at depth is not a subfile."""
        vault_root = tmp_path / "docs" / "vault"
        # Specs / 001 / checklists / sub / nested.md — scaffold at position 2
        file_path = vault_root / "Specs" / "001" / "checklists" / "sub" / "nested.md"
        assert _is_spec_subfile(file_path, vault_root) is False


class TestParseFrontmatter:
    """Tests for YAML frontmatter parsing from Markdown files."""

    def test_parses_valid_frontmatter(self, tmp_path: Path) -> None:
        """A valid YAML frontmatter block is parsed correctly."""
        md_file = tmp_path / "note.md"
        md_file.write_text(
            "---\ntitle: Test Note\ntags:\n  - type/design\ncreated: 2026-01-01\n"
            "updated: 2026-06-01\n---\n\nBody text.\n"
        )
        result = parse_frontmatter(md_file)
        assert result["title"] == "Test Note"
        assert result["tags"] == ["type/design"]
        assert "created" in result

    def test_empty_frontmatter_returns_empty_dict(self, tmp_path: Path) -> None:
        """A file with no frontmatter returns an empty dict."""
        md_file = tmp_path / "note.md"
        md_file.write_text("Just body text.\n")
        result = parse_frontmatter(md_file)
        assert result == {}

    def test_missing_file_returns_empty_dict(self, tmp_path: Path) -> None:
        """A non-existent file returns an empty dict."""
        result = parse_frontmatter(tmp_path / "nonexistent.md")
        assert result == {}

    def test_invalid_yaml_returns_empty_dict(self, tmp_path: Path) -> None:
        """Malformed YAML returns an empty dict."""
        md_file = tmp_path / "note.md"
        md_file.write_text("---\ntitle: [invalid\n---\n\nBody.\n")
        result = parse_frontmatter(md_file)
        assert result == {}

    def test_crlf_line_endings(self, tmp_path: Path) -> None:
        """Windows-style CRLF frontmatter delimiters are handled."""
        md_file = tmp_path / "note.md"
        md_file.write_bytes(
            b"---\r\ntitle: CRLF Note\r\ntags:\r\n  - type/design\r\n---\r\n\r\nBody.\r\n"
        )
        result = parse_frontmatter(md_file)
        assert result.get("title") == "CRLF Note"
        assert "type/design" in result.get("tags", [])

    def test_nfc_normalization(self, tmp_path: Path) -> None:
        """Frontmatter values are NFC-normalized."""
        md_file = tmp_path / "note.md"
        md_file.write_text("---\ntitle: caf\u00e9\n---\n\nBody.\n")
        result = parse_frontmatter(md_file)
        # already NFC
        assert result["title"] == "caf\u00e9"

    def test_non_dict_yaml_returns_empty(self, tmp_path: Path) -> None:
        """YAML that parses to a non-dict (e.g. a list) returns empty."""
        md_file = tmp_path / "note.md"
        md_file.write_text("---\n- item1\n- item2\n---\n\nBody.\n")
        result = parse_frontmatter(md_file)
        assert result == {}


class TestExtractWikilinks:
    """Tests for wikilink extraction from markdown text."""

    def test_simple_wikilink(self) -> None:
        """A basic [[Target]] is extracted."""
        result = extract_wikilinks("See [[Another Note]] for details.")
        assert result == ["Another Note"]

    def test_piped_wikilink(self) -> None:
        """[[Target|Display]] extracts the target, not the display."""
        result = extract_wikilinks("See [[Note|display name]].")
        assert result == ["Note"]

    def test_section_link(self) -> None:
        """[[Target#section]] extracts the target without the section."""
        result = extract_wikilinks("See [[Note#section]].")
        assert result == ["Note"]

    def test_attachment_skipped(self) -> None:
        """Attachment extensions (.png, .jpg, etc.) are skipped."""
        text = "![[image.png]] See [[Real Note]]."
        result = extract_wikilinks(text)
        assert result == ["Real Note"]

    def test_fenced_code_excluded(self) -> None:
        """Wikilinks inside fenced code blocks are excluded."""
        text = "```\n[[ShouldNotExtract]]\n```\n\n[[ShouldExtract]]"
        result = extract_wikilinks(text)
        assert result == ["ShouldExtract"]

    def test_inline_code_excluded(self) -> None:
        """Wikilinks inside inline code spans are excluded."""
        text = "See `[[DoNotExtract]]` and [[DoExtract]]."
        result = extract_wikilinks(text)
        assert result == ["DoExtract"]

    def test_leading_punct_inside_brackets_skipped(self) -> None:
        r"""Wikilink target starting with ! - \" ' $ inside [[ ]] is skipped."""
        text = "See [[!image.png]] and [[KeepMe]]."
        result = extract_wikilinks(text)
        assert result == ["KeepMe"]

    def test_nested_path_wikilink(self) -> None:
        """Wikilinks with path separators extract the full path."""
        result = extract_wikilinks("See [[Folder/Subfolder/Note]].")
        assert result == ["Folder/Subfolder/Note"]

    def test_no_wikilinks(self) -> None:
        """Text with no wikilinks returns an empty list."""
        result = extract_wikilinks("Just plain text with no links.")
        assert result == []

    def test_empty_string(self) -> None:
        """Empty string returns an empty list."""
        result = extract_wikilinks("")
        assert result == []

    def test_pdf_attachment_skipped(self) -> None:
        """PDF attachment embeds are skipped."""
        result = extract_wikilinks("![[document.pdf]]")
        assert result == []


class TestResolveNoteType:
    """Tests for _resolve_note_type."""

    def test_type_tag_from_tags_list(self) -> None:
        """A type/* tag in the tags list is resolved."""
        fm = {"tags": ["type/decision", "status/draft"]}
        assert _resolve_note_type(fm) == "type/decision"

    def test_bare_type_field(self) -> None:
        """A bare 'type' field is mapped to type/ prefix."""
        fm = {"type": "decision", "tags": []}
        assert _resolve_note_type(fm) == "type/decision"

    def test_bare_type_not_in_vocab(self) -> None:
        """A bare type not in the controlled vocabulary returns empty."""
        fm = {"type": "unknown-type", "tags": []}
        assert _resolve_note_type(fm) == ""

    def test_no_type_at_all(self) -> None:
        """No type tag or bare type field returns empty."""
        fm = {"tags": ["status/draft"]}
        assert _resolve_note_type(fm) == ""

    def test_tags_not_a_list(self) -> None:
        """If tags is not a list, treat as empty."""
        fm = {"tags": "not_a_list", "type": "decision"}
        assert _resolve_note_type(fm) == "type/decision"

    def test_multiple_type_tags_returns_empty(self) -> None:
        """Multiple type/* tags returns empty (ambiguous)."""
        fm = {"tags": ["type/decision", "type/design"]}
        assert _resolve_note_type(fm) == ""


class TestParseDateValue:
    """Tests for _parse_date_value."""

    def test_none_returns_none(self) -> None:
        """None input returns None."""
        assert _parse_date_value(None) is None

    def test_date_object(self) -> None:
        """A date object passes through."""
        d = date(2026, 6, 1)
        assert _parse_date_value(d) == d

    def test_datetime_object_converts_to_date(self) -> None:
        """A datetime object is converted to date."""
        dt = datetime(2026, 6, 1, 12, 30, 0)
        assert _parse_date_value(dt) == date(2026, 6, 1)

    def test_iso_date_string(self) -> None:
        """An ISO 8601 date string is parsed."""
        assert _parse_date_value("2026-06-01") == date(2026, 6, 1)

    def test_iso_datetime_string(self) -> None:
        """An ISO 8601 datetime string is parsed."""
        assert _parse_date_value("2026-06-01T12:30:00") == date(2026, 6, 1)

    def test_iso_datetime_with_tz(self) -> None:
        """An ISO 8601 datetime with timezone is parsed."""
        assert _parse_date_value("2026-06-01T12:30:00+0000") == date(2026, 6, 1)

    def test_iso_datetime_with_fractional(self) -> None:
        """An ISO 8601 datetime with fractional seconds is parsed."""
        assert _parse_date_value("2026-06-01T12:30:00.123456Z") == date(2026, 6, 1)

    def test_invalid_string_returns_none(self) -> None:
        """An unparseable string returns None."""
        assert _parse_date_value("not-a-date") is None

    def test_invalid_type_returns_none(self) -> None:
        """An invalid type (int) returns None."""
        assert _parse_date_value(42) is None

    def test_quoted_date_string(self) -> None:
        """A date string wrapped in quotes has quotes stripped."""
        assert _parse_date_value("'2026-06-01'") == date(2026, 6, 1)
        assert _parse_date_value('"2026-06-01"') == date(2026, 6, 1)


class TestValidateSchema:
    """Tests for frontmatter schema validation."""

    def test_valid_frontmatter_no_findings(self, tmp_path: Path) -> None:
        """A complete, valid frontmatter produces no findings."""
        fm = {
            "title": "Test",
            "type": "design",
            "tags": ["type/design", "status/draft"],
            "created": "2026-01-01",
            "updated": "2026-06-01",
        }
        findings = validate_schema(tmp_path / "note.md", fm, "note.md")
        assert len(findings) == 0

    def test_missing_frontmatter(self, tmp_path: Path) -> None:
        """An empty frontmatter dict produces a WARN."""
        findings = validate_schema(tmp_path / "note.md", {}, "note.md")
        assert any(
            f.severity == "WARN" and "no frontmatter" in f.message for f in findings
        )

    def test_missing_required_fields(self, tmp_path: Path) -> None:
        """Missing required fields produce ERROR findings."""
        fm = {"tags": ["type/design"]}
        findings = validate_schema(tmp_path / "note.md", fm, "note.md")
        missing_rules = {f.rule for f in findings}
        assert "missing_required_field" in missing_rules

    def test_missing_type_tag(self, tmp_path: Path) -> None:
        """No type tag at all produces an ERROR."""
        fm = {
            "title": "Test",
            "tags": ["status/draft"],
            "created": "2026-01-01",
            "updated": "2026-06-01",
        }
        findings = validate_schema(tmp_path / "note.md", fm, "note.md")
        assert any(f.rule == "missing_type_tag" for f in findings)

    def test_multiple_type_tags(self, tmp_path: Path) -> None:
        """Multiple type/* tags produce an ERROR."""
        fm = {
            "title": "Test",
            "tags": ["type/decision", "type/design"],
            "created": "2026-01-01",
            "updated": "2026-06-01",
        }
        findings = validate_schema(tmp_path / "note.md", fm, "note.md")
        assert any(f.rule == "multiple_type_tags" for f in findings)

    def test_invalid_type_tag(self, tmp_path: Path) -> None:
        """A type tag not in the controlled vocabulary produces an ERROR."""
        fm = {
            "title": "Test",
            "tags": ["type/bogus"],
            "created": "2026-01-01",
            "updated": "2026-06-01",
        }
        findings = validate_schema(tmp_path / "note.md", fm, "note.md")
        assert any(f.rule == "invalid_type_tag" for f in findings)

    def test_invalid_bare_type(self, tmp_path: Path) -> None:
        """A bare type field not in the controlled vocabulary produces an ERROR."""
        fm = {
            "title": "Test",
            "type": "bogus",
            "tags": [],
            "created": "2026-01-01",
            "updated": "2026-06-01",
        }
        findings = validate_schema(tmp_path / "note.md", fm, "note.md")
        assert any(f.rule == "invalid_type_tag" for f in findings)

    def test_invalid_status_tag(self, tmp_path: Path) -> None:
        """An invalid status/* tag produces an ERROR."""
        fm = {
            "title": "Test",
            "tags": ["type/design", "status/unknown-status"],
            "created": "2026-01-01",
            "updated": "2026-06-01",
        }
        findings = validate_schema(tmp_path / "note.md", fm, "note.md")
        assert any(f.rule == "invalid_status_tag" for f in findings)

    def test_invalid_domain_tag(self, tmp_path: Path) -> None:
        """An invalid domain/* tag produces an ERROR."""
        fm = {
            "title": "Test",
            "tags": ["type/design", "domain/unknown-domain"],
            "created": "2026-01-01",
            "updated": "2026-06-01",
        }
        findings = validate_schema(tmp_path / "note.md", fm, "note.md")
        assert any(f.rule == "invalid_domain_tag" for f in findings)

    def test_agent_note_missing_aliases_and_source(self, tmp_path: Path) -> None:
        """Agent note types (decision, discovery, session-log) require aliases and source."""
        for nt in AGENT_NOTE_TYPES:
            fm = {
                "title": "Test",
                "tags": [nt, "status/draft"],
                "created": "2026-01-01",
                "updated": "2026-06-01",
            }
            findings = validate_schema(tmp_path / "note.md", fm, "note.md")
            assert any(f.rule == "missing_aliases" for f in findings)
            assert any(f.rule == "missing_source" for f in findings)

    def test_grounded_note_missing_code_refs(self, tmp_path: Path) -> None:
        """Grounded note types (decision, discovery) require code-refs."""
        for nt in GROUNDED_NOTE_TYPES:
            fm = {
                "title": "Test",
                "tags": [nt, "status/draft"],
                "aliases": ["alias1"],
                "source": "test",
                "created": "2026-01-01",
                "updated": "2026-06-01",
            }
            findings = validate_schema(tmp_path / "note.md", fm, "note.md")
            assert any(f.rule == "missing_code_refs" for f in findings)

    def test_invalid_date_created(self, tmp_path: Path) -> None:
        """An invalid created date produces an ERROR."""
        fm = {
            "title": "Test",
            "tags": ["type/design"],
            "created": "bad-date",
            "updated": "2026-06-01",
        }
        findings = validate_schema(tmp_path / "note.md", fm, "note.md")
        assert any(
            f.rule == "invalid_date" and "created" in f.message for f in findings
        )

    def test_invalid_date_updated(self, tmp_path: Path) -> None:
        """An invalid updated date produces an ERROR."""
        fm = {
            "title": "Test",
            "tags": ["type/design"],
            "created": "2026-01-01",
            "updated": "bad-date",
        }
        findings = validate_schema(tmp_path / "note.md", fm, "note.md")
        assert any(
            f.rule == "invalid_date" and "updated" in f.message for f in findings
        )

    def test_non_string_tags_skipped(self, tmp_path: Path) -> None:
        """Non-string tags are skipped without error."""
        fm = {
            "title": "Test",
            "tags": ["type/design", 42],
            "created": "2026-01-01",
            "updated": "2026-06-01",
        }
        findings = validate_schema(tmp_path / "note.md", fm, "note.md")
        # No invalid_* findings for the int tag
        assert not any(f.rule.startswith("invalid_") for f in findings)

    def test_unknown_tag_prefix_skipped(self, tmp_path: Path) -> None:
        """A tag with an unknown prefix (not type/status/domain) is skipped."""
        fm = {
            "title": "Test",
            "tags": ["type/design", "custom/whatever"],
            "created": "2026-01-01",
            "updated": "2026-06-01",
        }
        findings = validate_schema(tmp_path / "note.md", fm, "note.md")
        assert not any("custom/whatever" in f.message for f in findings)


########################################################################
# VaultAuditService tests
########################################################################


class TestVaultAuditServiceInit:
    """Tests for VaultAuditService.__init__."""

    def test_init_with_default(self) -> None:
        """Default vault_dir is 'docs/vault'."""
        service = VaultAuditService()
        assert str(service.vault_dir) == "docs/vault"

    def test_init_with_custom_dir(self) -> None:
        """Custom vault_dir is accepted."""
        service = VaultAuditService(vault_dir="/custom/path")
        assert str(service.vault_dir) == "/custom/path"

    @patch("anvil.services.vault.vault_audit.yaml", None)
    def test_init_raises_when_yaml_missing(self) -> None:
        """ImportError is raised when PyYAML is not available."""
        with pytest.raises(ImportError, match="PyYAML is required"):
            VaultAuditService()


class TestVaultAuditServiceBuildFilenameIndex:
    """Tests for build_filename_index."""

    def test_returns_index(self, tmp_path: Path) -> None:
        """Returns a stem->path mapping for all .md files."""
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "note1.md").write_text("# Note 1")
        sub = vault / "sub"
        sub.mkdir(parents=True)
        (sub / "note2.md").write_text("# Note 2")

        service = VaultAuditService(vault_dir=str(vault))
        index = service.build_filename_index()
        assert "note1" in index
        assert "note2" in index
        assert any("sub" in str(p) for p in index["note2"])

    def test_nonexistent_vault_returns_empty(self, tmp_path: Path) -> None:
        """A non-existent vault directory returns an empty index."""
        service = VaultAuditService(vault_dir=str(tmp_path / "nonexistent"))
        index = service.build_filename_index()
        assert index == {}


class TestVaultAuditServiceMechanicalAudit:
    """Tests for _run_mechanical_audit_sync and run_mechanical_audit."""

    def test_vault_not_found(self, tmp_path: Path) -> None:
        """When vault_dir does not exist, an ERROR finding is produced."""
        service = VaultAuditService(vault_dir=str(tmp_path / "nonexistent"))
        report = service._run_mechanical_audit_sync()
        assert len(report.errors) == 1
        assert report.errors[0].rule == "vault_not_found"

    def test_scans_markdown_files(self, tmp_path: Path) -> None:
        """Markdown files are scanned and counted in stats."""
        vault = tmp_path / "vault"
        vault.mkdir()
        # Create a valid .md file with proper frontmatter
        note = vault / "test-note.md"
        note.write_text(
            "---\ntitle: Test\ntype: design\ntags:\n  - type/design\n  - status/draft\n"
            "created: 2026-01-01\nupdated: 2026-06-01\n---\n\nBody text without wikilinks.\n"
        )
        service = VaultAuditService(vault_dir=str(vault))
        report = service._run_mechanical_audit_sync()
        assert report.stats.get("files_scanned") == 1
        assert len(report.errors) == 0
        assert len(report.warnings) == 0

    def test_ignores_meta_dir(self, tmp_path: Path) -> None:
        """Files under _meta/ are skipped during validation but counted in files_scanned."""
        vault = tmp_path / "vault"
        vault.mkdir()
        meta_dir = vault / "_meta"
        meta_dir.mkdir()
        (meta_dir / "tags.md").write_text("# Tags")
        note = vault / "real-note.md"
        note.write_text(
            "---\ntitle: Real\ntype: design\ntags:\n  - type/design\n"
            "created: 2026-01-01\nupdated: 2026-06-01\n---\n\nBody.\n"
        )
        service = VaultAuditService(vault_dir=str(vault))
        report = service._run_mechanical_audit_sync()
        # files_scanned includes ALL .md files (even skipped ones)
        assert report.stats.get("files_scanned") == 2
        # But only the valid note is in the scannable list (no errors from _meta)
        assert len(report.errors) == 0

    def test_scaffold_file_skipped(self, tmp_path: Path) -> None:
        """Scaffold files generate SKIPPED entries and are not validated."""
        vault = tmp_path / "vault"
        vault.mkdir()
        specs = vault / "Specs" / "001 Design" / "checklists"
        specs.mkdir(parents=True)
        (specs / "items.md").write_text("Tool-generated checklist.\n")
        note = vault / "note.md"
        note.write_text(
            "---\ntitle: Real\ntype: design\ntags:\n  - type/design\n"
            "created: 2026-01-01\nupdated: 2026-06-01\n---\n\nBody.\n"
        )
        service = VaultAuditService(vault_dir=str(vault))
        report = service._run_mechanical_audit_sync()
        assert len(report.skipped) == 1
        assert report.skipped[0].rule == "skipped_scaffold"

    def test_broken_wikilink_detected(self, tmp_path: Path) -> None:
        """A wikilink to a non-existent file produces an ERROR."""
        vault = tmp_path / "vault"
        vault.mkdir()
        note = vault / "source.md"
        note.write_text(
            "---\ntitle: Source\ntype: design\ntags:\n  - type/design\n"
            "created: 2026-01-01\nupdated: 2026-06-01\n---\n\nSee [[MissingNote]].\n"
        )
        service = VaultAuditService(vault_dir=str(vault))
        report = service._run_mechanical_audit_sync()
        assert any(f.rule == "broken_wikilink" for f in report.errors)

    def test_read_error(self, tmp_path: Path) -> None:
        """An unreadable file produces an ERROR."""
        vault = tmp_path / "vault"
        vault.mkdir()
        note = vault / "locked.md"
        note.write_text(
            "---\ntitle: Locked\ntype: design\ntags:\n  - type/design\n"
            "created: 2026-01-01\nupdated: 2026-06-01\n---\n\nBody.\n"
        )
        # Remove read permission
        note.chmod(0o000)
        try:
            service = VaultAuditService(vault_dir=str(vault))
            report = service._run_mechanical_audit_sync()
            assert any(f.rule == "read_error" for f in report.errors)
        finally:
            note.chmod(0o644)

    def test_duplicate_filename_warning(self, tmp_path: Path) -> None:
        """Duplicate filename stems produce WARN findings."""
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "same-name.md").write_text(
            "---\ntitle: One\ntype: design\ntags:\n  - type/design\n"
            "created: 2026-01-01\nupdated: 2026-06-01\n---\n\nBody.\n"
        )
        sub = vault / "sub"
        sub.mkdir()
        (sub / "same-name.md").write_text(
            "---\ntitle: Two\ntype: design\ntags:\n  - type/design\n"
            "created: 2026-01-01\nupdated: 2026-06-01\n---\n\nBody.\n"
        )
        service = VaultAuditService(vault_dir=str(vault))
        report = service._run_mechanical_audit_sync()
        assert any(f.rule == "duplicate_filename" for f in report.warnings)

    @pytest.mark.asyncio
    async def test_run_mechanical_audit_async(self, tmp_path: Path) -> None:
        """The async wrapper delegates to the sync method."""
        vault = tmp_path / "vault"
        vault.mkdir()
        note = vault / "note.md"
        note.write_text(
            "---\ntitle: Test\ntype: design\ntags:\n  - type/design\n"
            "created: 2026-01-01\nupdated: 2026-06-01\n---\n\nBody.\n"
        )
        service = VaultAuditService(vault_dir=str(vault))
        report = await service.run_mechanical_audit()
        assert isinstance(report, MechanicalReport)
        assert report.stats.get("files_scanned") == 1

    def test_notes_with_issues_stat(self, tmp_path: Path) -> None:
        """stats['notes_with_issues'] is set correctly."""
        vault = tmp_path / "vault"
        vault.mkdir()
        # Note with broken wikilink
        note = vault / "source.md"
        note.write_text(
            "---\ntitle: Source\ntype: design\ntags:\n  - type/design\n"
            "created: 2026-01-01\nupdated: 2026-06-01\n---\n\n[[Missing]].\n"
        )
        service = VaultAuditService(vault_dir=str(vault))
        report = service._run_mechanical_audit_sync()
        expected = len(report.errors) + len(report.warnings)
        assert report.stats.get("notes_with_issues") == expected

    def test_spec_subfile_not_duplicate(self, tmp_path: Path) -> None:
        """Spec subfiles are excluded from duplicate-filename detection."""
        vault = tmp_path / "vault"
        vault.mkdir()
        # Create a spec dir with root note and subfiles
        specs_dir = vault / "Specs" / "001 Design"
        specs_dir.mkdir(parents=True)
        root = specs_dir / "001 Design.md"
        root.write_text(
            "---\ntitle: Design\ntype: spec\ntags:\n  - type/spec\n"
            "created: 2026-01-01\nupdated: 2026-06-01\n---\n\nBody.\n"
        )
        plan = specs_dir / "001 Design - plan.md"
        plan.write_text(
            "---\ntitle: Plan\ntags:\n  - type/spec\n"
            "created: 2026-01-01\nupdated: 2026-06-01\n---\n\nPlan.\n"
        )
        # Root note and spec subfile have same stem "001 Design" — no duplicate warning
        service = VaultAuditService(vault_dir=str(vault))
        report = service._run_mechanical_audit_sync()
        assert not any(f.rule == "duplicate_filename" for f in report.warnings)

    def test_skip_obsidian_and_addons(self, tmp_path: Path) -> None:
        """Files under .obsidian/ and addons/ are excluded from validation."""
        vault = tmp_path / "vault"
        vault.mkdir()
        obsidian = vault / ".obsidian"
        obsidian.mkdir()
        (obsidian / "config.md").write_text("# config")
        addons = vault / "addons"
        addons.mkdir()
        (addons / "plugin.md").write_text("# plugin")
        note = vault / "real.md"
        note.write_text(
            "---\ntitle: Real\ntype: design\ntags:\n  - type/design\n"
            "created: 2026-01-01\nupdated: 2026-06-01\n---\n\nBody.\n"
        )
        service = VaultAuditService(vault_dir=str(vault))
        report = service._run_mechanical_audit_sync()
        # files_scanned includes ALL .md files including skipped ones
        assert report.stats.get("files_scanned") == 3
        # No errors or warnings from the skipped files
        assert len(report.errors) == 0

    def test_non_md_files_ignored(self, tmp_path: Path) -> None:
        """Non-.md files are ignored by rglob('*.md')."""
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "data.json").write_text("{}")
        note = vault / "real.md"
        note.write_text(
            "---\ntitle: Real\ntype: design\ntags:\n  - type/design\n"
            "created: 2026-01-01\nupdated: 2026-06-01\n---\n\nBody.\n"
        )
        service = VaultAuditService(vault_dir=str(vault))
        report = service._run_mechanical_audit_sync()
        assert report.stats.get("files_scanned") == 1
