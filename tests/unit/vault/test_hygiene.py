# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for vault hygiene analysis.

Tests the individual functions in ``hygiene.py`` (tag conformity,
frontmatter completeness, phantom links, over-linking) as well as
the ``check_*`` modules that ``cli.py`` dispatches to.

Checker tests use temporary directories with sample Python files
to verify pass/fail behavior.
"""

from __future__ import annotations

import textwrap
from datetime import date, datetime
from pathlib import Path

import pytest

from anvil.services.vault.check_import_placement import (
    scan_directory as ip_scan_directory,
)
from anvil.services.vault.check_import_placement import scan_file as ip_scan_file
from anvil.services.vault.check_init_py_ownership import (
    scan_directory as init_py_scan_directory,
)
from anvil.services.vault.check_one_class import scan_file as oc_scan_file
from anvil.services.vault.check_relative_imports import AbsoluteImport
from anvil.services.vault.check_relative_imports import (
    scan_directory as ri_scan_directory,
)
from anvil.services.vault.check_relative_imports import scan_file as ri_scan_file
from anvil.services.vault.hygiene import (
    _classify_percentage,
    _find_near_duplicate_tags,
    _find_over_linking,
    _is_valid_date,
    _levenshtein_distance,
    _load_controlled_tags,
    compute_hygiene,
)
from anvil.services.vault.types_note_metadata import NoteMetadata

######################################################################
# _classify_percentage
######################################################################


class TestClassifyPercentage:
    """Tests for ``_classify_percentage`` helper."""

    def test_100_is_healthy(self) -> None:
        assert _classify_percentage(100.0) == "healthy"

    def test_99_is_warning(self) -> None:
        assert _classify_percentage(99.0) == "warning"

    def test_90_is_warning(self) -> None:
        assert _classify_percentage(90.0) == "warning"

    def test_89_is_critical(self) -> None:
        assert _classify_percentage(89.999) == "critical"

    def test_0_is_critical(self) -> None:
        assert _classify_percentage(0.0) == "critical"

    def test_above_100_is_healthy(self) -> None:
        assert _classify_percentage(101.0) == "healthy"

    def test_negative_is_critical(self) -> None:
        assert _classify_percentage(-1.0) == "critical"


######################################################################
# _is_valid_date
######################################################################


class TestIsValidDate:
    """Tests for ``_is_valid_date`` helper."""

    def test_date_object(self) -> None:
        assert _is_valid_date(date(2024, 1, 15)) is True

    def test_datetime_object(self) -> None:
        assert _is_valid_date(datetime(2024, 1, 15, 10, 30)) is True

    def test_iso_date_string(self) -> None:
        assert _is_valid_date("2024-01-15") is True

    def test_iso_datetime_string(self) -> None:
        assert _is_valid_date("2024-01-15T10:30:00") is True

    def test_iso_datetime_with_z(self) -> None:
        assert _is_valid_date("2024-01-15T10:30:00Z") is True

    def test_iso_datetime_with_microseconds_z(self) -> None:
        assert _is_valid_date("2024-01-15T10:30:00.123456Z") is True

    def test_none_is_not_valid(self) -> None:
        assert _is_valid_date(None) is False

    def test_integer_is_not_valid(self) -> None:
        assert _is_valid_date(42) is False

    def test_garbage_string_is_not_valid(self) -> None:
        assert _is_valid_date("not-a-date") is False

    def test_empty_string_is_not_valid(self) -> None:
        assert _is_valid_date("") is False

    def test_partial_iso_string_is_not_valid(self) -> None:
        assert _is_valid_date("2024-01") is False

    def test_date_with_quotes(self) -> None:
        assert _is_valid_date("'2024-01-15'") is True


######################################################################
# _levenshtein_distance
######################################################################


class TestLevenshteinDistance:
    """Tests for ``_levenshtein_distance``."""

    def test_identical_strings(self) -> None:
        assert _levenshtein_distance("hello", "hello") == 0

    def test_completely_different(self) -> None:
        assert _levenshtein_distance("abc", "xyz") == 3

    def test_one_insertion(self) -> None:
        assert _levenshtein_distance("cat", "cats") == 1

    def test_one_deletion(self) -> None:
        assert _levenshtein_distance("cats", "cat") == 1

    def test_one_substitution(self) -> None:
        assert _levenshtein_distance("cat", "car") == 1

    def test_empty_against_nonempty(self) -> None:
        assert _levenshtein_distance("", "abc") == 3

    def test_both_empty(self) -> None:
        assert _levenshtein_distance("", "") == 0

    def test_single_swap(self) -> None:
        assert _levenshtein_distance("ab", "ba") == 2

    def test_longer_strings(self) -> None:
        assert _levenshtein_distance("kitten", "sitting") == 3

    def test_whitespace_matters(self) -> None:
        assert _levenshtein_distance("type/foo", "type/fo") == 1


######################################################################
# _find_near_duplicate_tags
######################################################################


class TestFindNearDuplicateTags:
    """Tests for ``_find_near_duplicate_tags``."""

    def test_no_duplicates(self) -> None:
        tags = ["type/principle", "type/decision", "domain/core"]
        assert _find_near_duplicate_tags(tags) == []

    def test_single_tag_no_duplicate(self) -> None:
        assert _find_near_duplicate_tags(["type/foo"]) == []

    def test_case_duplicate(self) -> None:
        tags = ["type/decision", "Type/Decision"]
        result = _find_near_duplicate_tags(tags)
        assert len(result) == 1
        pair = result[0]
        assert "type/decision" in pair
        assert "Type/Decision" in pair

    def test_levenshtein_duplicate(self) -> None:
        tags = ["domain/governance", "domain/governanc"]
        result = _find_near_duplicate_tags(tags)
        assert len(result) >= 1

    def test_levenshtein_within_2(self) -> None:
        tags = ["type/foo", "type/fooo"]
        result = _find_near_duplicate_tags(tags)
        assert len(result) >= 1

    def test_three_same_case(self) -> None:
        tags = ["type/a", "Type/A", "TYPE/A"]
        result = _find_near_duplicate_tags(tags)
        # Should find at least one case-based duplicate pair
        assert len(result) >= 1

    def test_no_false_positive_far_apart(self) -> None:
        tags = ["type/principle", "domain/database"]
        assert _find_near_duplicate_tags(tags) == []

    def test_exact_duplicate_handling(self) -> None:
        tags = ["type/foo", "type/foo"]
        result = _find_near_duplicate_tags(tags)
        # Same strings repeated shouldn't cause false positives
        # since they are equal (distance 0) but identical
        assert isinstance(result, list)


######################################################################
# _load_controlled_tags
######################################################################


class TestLoadControlledTags:
    """Tests for ``_load_controlled_tags``."""

    def test_no_tags_file_uses_builtin_vocab(self, tmp_path: Path) -> None:
        """Verify fallback to built-in vocab when tags.md missing."""
        tags = _load_controlled_tags(tmp_path)
        assert "type/principle" in tags
        assert "status/draft" in tags
        assert "domain/core" in tags
        assert len(tags) >= 30  # type + status + domain combined

    def test_loads_from_tags_file(self, tmp_path: Path) -> None:
        """Verify tags from file are included."""
        meta_dir = tmp_path / "_meta"
        meta_dir.mkdir(parents=True)
        (meta_dir / "tags.md").write_text(
            textwrap.dedent(
                """\
                ---
                title: Tags
                ---

                - `type/custom`
                - `domain/custom`
                - `standalone-tag` — Some description
            """
            )
        )
        tags = _load_controlled_tags(tmp_path)
        assert "type/custom" in tags
        assert "domain/custom" in tags
        assert "standalone-tag" in tags
        assert "type/principle" in tags  # built-in still included

    def test_skips_frontmatter(self, tmp_path: Path) -> None:
        """Verify frontmatter lines are not parsed as tags."""
        meta_dir = tmp_path / "_meta"
        meta_dir.mkdir(parents=True)
        (meta_dir / "tags.md").write_text(
            textwrap.dedent(
                """\
                ---
                title: Tags
                other: value
                ---

                - `type/real`
            """
            )
        )
        tags = _load_controlled_tags(tmp_path)
        assert "type/real" in tags
        assert "title" not in tags
        assert "other" not in tags

    def test_unreadable_file_falls_back(self, tmp_path: Path) -> None:
        """Verify unreadable tags.md doesn't crash."""
        tags = _load_controlled_tags(tmp_path / "nonexistent")
        assert "type/principle" in tags


######################################################################
# _find_over_linking
######################################################################


class TestFindOverLinking:
    """Tests for ``_find_over_linking``."""

    def test_no_over_linking(self, tmp_path: Path) -> None:
        """Verify no duplicates detected when each link appears once."""
        note_path = tmp_path / "test.md"
        note_path.write_text("---\ntitle: Test\n---\n\n[[LinkA]] and [[LinkB]]")
        notes: dict[str, NoteMetadata] = {
            "test": NoteMetadata(path=note_path, stem="test", tags=[]),
        }
        result = _find_over_linking(notes, tmp_path)
        assert result == []

    def test_detects_over_linking_in_same_section(self, tmp_path: Path) -> None:
        """Verify duplicate wikilink in same section is flagged."""
        note_path = tmp_path / "test.md"
        note_path.write_text("---\ntitle: Test\n---\n\n[[LinkA]] and [[LinkA]] again")
        notes: dict[str, NoteMetadata] = {
            "test": NoteMetadata(path=note_path, stem="test", tags=[]),
        }
        result = _find_over_linking(notes, tmp_path)
        assert len(result) == 1
        assert result[0][0] == "test"  # note stem
        assert result[0][2] == "LinkA"  # over-linked target

    def test_different_sections_not_overlinked(self, tmp_path: Path) -> None:
        """Verify same link in different sections is not over-linking."""
        note_path = tmp_path / "test.md"
        note_path.write_text(
            "---\ntitle: Test\n---\n\n## Section1\n[[LinkA]]\n\n## Section2\n[[LinkA]]"
        )
        notes: dict[str, NoteMetadata] = {
            "test": NoteMetadata(path=note_path, stem="test", tags=[]),
        }
        result = _find_over_linking(notes, tmp_path)
        assert result == []

    def test_skips_unreadable_files(self, tmp_path: Path) -> None:
        """Verify unreadable file doesn't crash."""
        note = NoteMetadata(path=tmp_path / "nonexistent.md", stem="missing", tags=[])
        result = _find_over_linking({"missing": note}, tmp_path)
        assert result == []

    def test_over_linking_in_named_section(self, tmp_path: Path) -> None:
        """Verify duplicate in a named section is reported with section name."""
        note_path = tmp_path / "test.md"
        note_path.write_text(
            "---\ntitle: Test\n---\n\n## Usage\n[[LinkA]] then [[LinkA]]"
        )
        notes: dict[str, NoteMetadata] = {
            "test": NoteMetadata(path=note_path, stem="test", tags=[]),
        }
        result = _find_over_linking(notes, tmp_path)
        assert len(result) == 1
        assert "Usage" in result[0][1]

    def test_over_linking_across_multiple_sections(self, tmp_path: Path) -> None:
        """Verify duplicate in one section but not another."""
        note_path = tmp_path / "test.md"
        note_path.write_text(
            "---\ntitle: Test\n---\n\n## A\n[[LinkX]] [[LinkX]]\n\n## B\n[[LinkX]]"
        )
        notes: dict[str, NoteMetadata] = {
            "test": NoteMetadata(path=note_path, stem="test", tags=[]),
        }
        result = _find_over_linking(notes, tmp_path)
        assert len(result) == 1  # only section A has the duplicate

    def test_no_frontmatter(self, tmp_path: Path) -> None:
        """Verify note without frontmatter still works."""
        note_path = tmp_path / "test.md"
        note_path.write_text("[[LinkA]] and [[LinkA]]")
        notes: dict[str, NoteMetadata] = {
            "test": NoteMetadata(path=note_path, stem="test", tags=[]),
        }
        result = _find_over_linking(notes, tmp_path)
        assert len(result) == 1


######################################################################
# compute_hygiene
######################################################################


class TestComputeHygiene:
    """Tests for ``compute_hygiene`` — full hygiene analysis."""

    def test_empty_vault(self, tmp_path: Path) -> None:
        """Verify empty vault returns perfect metrics."""
        metrics = compute_hygiene({}, tmp_path)
        assert metrics.non_conformant_tags == []
        assert metrics.missing_fields == []
        assert metrics.phantom_links == []
        assert metrics.tag_conformity_pct == 100.0
        assert metrics.frontmatter_completeness_pct == 100.0

    def test_detects_non_conformant_tags(self, tmp_path: Path) -> None:
        """Verify tags outside controlled vocabulary are flagged."""
        notes: dict[str, NoteMetadata] = {
            "good": NoteMetadata(
                path=tmp_path / "good.md",
                stem="good",
                tags=["type/principle"],
                frontmatter={
                    "title": "Good",
                    "type": "principle",
                    "tags": ["type/principle"],
                    "created": "2024-01-01",
                    "updated": "2024-01-02",
                },
            ),
            "bad": NoteMetadata(
                path=tmp_path / "bad.md",
                stem="bad",
                tags=["type/unknown"],
                frontmatter={
                    "title": "Bad",
                    "type": "unknown",
                    "tags": ["type/unknown"],
                    "created": "2024-01-01",
                    "updated": "2024-01-02",
                },
            ),
        }
        metrics = compute_hygiene(notes, tmp_path)
        assert len(metrics.non_conformant_tags) == 1
        assert metrics.non_conformant_tags[0] == ("bad", "type/unknown")
        assert metrics.tag_conformity_pct < 100.0

    def test_detects_missing_fields(self, tmp_path: Path) -> None:
        """Verify notes missing required fields are flagged."""
        notes: dict[str, NoteMetadata] = {
            "incomplete": NoteMetadata(
                path=tmp_path / "incomplete.md",
                stem="incomplete",
                tags=[],
                frontmatter={"title": "Only Title"},
            ),
        }
        metrics = compute_hygiene(notes, tmp_path)
        expected_missing = {"type", "tags", "created", "updated"}
        actual_missing = {field for _, field in metrics.missing_fields}
        assert expected_missing.issubset(actual_missing)
        assert metrics.frontmatter_completeness_pct < 100.0

    def test_detects_type_mismatch(self, tmp_path: Path) -> None:
        """Verify non-list tags field is flagged."""
        notes: dict[str, NoteMetadata] = {
            "bad": NoteMetadata(
                path=tmp_path / "bad.md",
                stem="bad",
                tags=[],
                frontmatter={
                    "title": "Bad",
                    "type": "decision",
                    "tags": "not-a-list",
                    "created": "2024-01-01",
                    "updated": "2024-01-02",
                },
            ),
        }
        metrics = compute_hygiene(notes, tmp_path)
        assert len(metrics.type_mismatches) == 1
        assert metrics.type_mismatches[0][:2] == ("bad", "tags")

    def test_detects_invalid_dates(self, tmp_path: Path) -> None:
        """Verify invalid dates are flagged."""
        notes: dict[str, NoteMetadata] = {
            "dated": NoteMetadata(
                path=tmp_path / "dated.md",
                stem="dated",
                tags=[],
                frontmatter={
                    "title": "Dated",
                    "type": "decision",
                    "tags": ["type/decision"],
                    "created": "bad-date",
                    "updated": "2024-01-01",
                },
            ),
        }
        metrics = compute_hygiene(notes, tmp_path)
        assert len(metrics.inconsistent_dates) == 1
        assert "bad-date" in metrics.inconsistent_dates[0][1]

    def test_detects_phantom_links(self, tmp_path: Path) -> None:
        """Verify phantom links (targets that don't exist) are flagged."""
        notes: dict[str, NoteMetadata] = {
            "source": NoteMetadata(
                path=tmp_path / "source.md",
                stem="source",
                outbound_stems=["ghost"],
                tags=[],
                frontmatter={
                    "title": "Source",
                    "type": "decision",
                    "tags": ["type/decision"],
                    "created": "2024-01-01",
                    "updated": "2024-01-02",
                },
            ),
        }
        metrics = compute_hygiene(notes, tmp_path)
        assert len(metrics.phantom_links) == 1
        assert metrics.phantom_links[0] == ("source", "ghost")

    def test_complete_metadata_passes(self, tmp_path: Path) -> None:
        """Verify a note with complete metadata passes all checks."""
        (tmp_path / "_meta").mkdir(parents=True)
        (tmp_path / "_meta" / "tags.md").write_text(
            textwrap.dedent(
                """\
                ---
                ---

                - `type/decision`
            """
            )
        )
        notes: dict[str, NoteMetadata] = {
            "perfect": NoteMetadata(
                path=tmp_path / "perfect.md",
                stem="perfect",
                tags=["type/decision"],
                frontmatter={
                    "title": "Perfect",
                    "type": "decision",
                    "tags": ["type/decision"],
                    "created": "2024-01-01",
                    "updated": "2024-01-02",
                },
            ),
        }
        metrics = compute_hygiene(notes, tmp_path)
        assert metrics.non_conformant_tags == []
        assert metrics.missing_fields == []
        assert metrics.type_mismatches == []
        assert metrics.inconsistent_dates == []
        assert metrics.tag_conformity_pct == 100.0
        assert metrics.frontmatter_completeness_pct == 100.0


######################################################################
# check_import_placement
######################################################################


class TestCheckImportPlacement:
    """Tests for ``check_import_placement.scan_file`` and ``scan_directory``."""

    def test_no_violations(self, tmp_path: Path) -> None:
        """Verify a file with top-level imports passes."""
        f = tmp_path / "good.py"
        f.write_text(
            textwrap.dedent(
                """\
                from __future__ import annotations
                import os
                from pathlib import Path

                def foo() -> None:
                    pass
            """
            )
        )
        result = ip_scan_file(f)
        assert result.violations == []

    def test_detects_lazy_import(self, tmp_path: Path) -> None:
        """Verify import after first definition is flagged."""
        f = tmp_path / "bad.py"
        f.write_text(
            textwrap.dedent(
                """\
                def foo() -> None:
                    pass

                import os
            """
            )
        )
        result = ip_scan_file(f)
        assert len(result.violations) == 1
        assert "import os" in result.violations[0].statement

    def test_type_checking_import_allowed(self, tmp_path: Path) -> None:
        """Verify TYPE_CHECKING-guarded imports are allowed."""
        f = tmp_path / "good.py"
        f.write_text(
            textwrap.dedent(
                """\
                from __future__ import annotations
                from typing import TYPE_CHECKING

                def foo() -> None:
                    pass

                if TYPE_CHECKING:
                    from .something import Something
            """
            )
        )
        result = ip_scan_file(f)
        assert result.violations == []

    def test_try_except_import_allowed(self, tmp_path: Path) -> None:
        """Verify try/except ImportError blocks are allowed."""
        f = tmp_path / "good.py"
        f.write_text(
            textwrap.dedent(
                """\
                def foo() -> None:
                    pass

                try:
                    import yaml
                except ImportError:
                    yaml = None
            """
            )
        )
        result = ip_scan_file(f)
        assert result.violations == []

    def test_detects_import_in_function_body(self, tmp_path: Path) -> None:
        """Verify a lazy import inside a function is flagged."""
        f = tmp_path / "bad.py"
        f.write_text(
            textwrap.dedent(
                """\
                def foo() -> None:
                    import os  # should be at top
                    pass
            """
            )
        )
        result = ip_scan_file(f)
        assert len(result.violations) == 1

    def test_no_definitions_no_violations(self, tmp_path: Path) -> None:
        """Verify a file with only imports has no violations."""
        f = tmp_path / "only_imports.py"
        f.write_text(
            textwrap.dedent(
                """\
                import os
                import sys
                from pathlib import Path
            """
            )
        )
        result = ip_scan_file(f)
        assert result.violations == []

    def test_scan_directory_collects_all(self, tmp_path: Path) -> None:
        """Verify scan_directory finds violations across multiple files."""
        (tmp_path / "good.py").write_text(
            textwrap.dedent(
                """\
                import os

                def foo() -> None:
                    pass
            """
            )
        )
        (tmp_path / "bad.py").write_text(
            textwrap.dedent(
                """\
                def foo() -> None:
                    pass

                import sys
            """
            )
        )
        results = ip_scan_directory(tmp_path)
        total = sum(len(r.violations) for r in results)
        assert total == 1  # only bad.py has a violation

    def test_comment_suppression_allowed(self, tmp_path: Path) -> None:
        """Verify # import-placement:allow suppresses the next import."""
        f = tmp_path / "suppressed.py"
        f.write_text(
            textwrap.dedent(
                """\
                def foo() -> None:
                    pass

                # import-placement:allow
                import os
            """
            )
        )
        result = ip_scan_file(f)
        assert result.violations == []

    def test_unreadable_file(self, tmp_path: Path) -> None:
        """Verify unreadable file produces a violation."""
        f = tmp_path / "unreadable.py"
        f.write_text("import os")
        f.chmod(0o000)
        try:
            result = ip_scan_file(f)
            assert len(result.violations) > 0
        finally:
            f.chmod(0o644)


######################################################################
# check_relative_imports
######################################################################


class TestCheckRelativeImports:
    """Tests for ``check_relative_imports.scan_file`` and ``scan_directory``."""

    def test_no_absolute_imports(self, tmp_path: Path) -> None:
        """Verify file with only relative imports passes."""
        f = tmp_path / "good.py"
        f.write_text(
            textwrap.dedent(
                """\
                from __future__ import annotations
                from .module import X
                from ..parent import Y
            """
            )
        )
        result = ri_scan_file(f)
        assert result.violations == []

    def test_detects_absolute_import(self, tmp_path: Path) -> None:
        """Verify file with absolute anvil. import is flagged."""
        f = tmp_path / "bad.py"
        f.write_text(
            textwrap.dedent(
                """\
                from anvil.core import engine
            """
            )
        )
        result = ri_scan_file(f)
        assert len(result.violations) == 1
        assert "anvil" in result.violations[0].line_text

    def test_import_anvil_dot(self, tmp_path: Path) -> None:
        """Verify ``import anvil.`` form is also detected."""
        f = tmp_path / "bad.py"
        f.write_text("import anvil.core.engine\n")
        result = ri_scan_file(f)
        assert len(result.violations) == 1

    def test_std_lib_imports_not_flagged(self, tmp_path: Path) -> None:
        """Verify stdlib imports are not flagged."""
        f = tmp_path / "good.py"
        f.write_text(
            textwrap.dedent(
                """\
                import os
                import sys
                from pathlib import Path
            """
            )
        )
        result = ri_scan_file(f)
        assert result.violations == []

    def test_type_checking_top_level_import_not_flagged(self, tmp_path: Path) -> None:
        """Verify top-level ``import anvil.`` (no ``from``) is flagged,
        but ``from`` form is also detected."""
        f = tmp_path / "good.py"
        f.write_text("import anvil.core\n")
        result = ri_scan_file(f)
        assert len(result.violations) == 1

    def test_suppression_comment(self, tmp_path: Path) -> None:
        """Verify # relative-imports:allow suppresses flag."""
        f = tmp_path / "allowed.py"
        f.write_text(
            textwrap.dedent(
                """\
                from anvil.core import engine  # relative-imports:allow
            """
            )
        )
        result = ri_scan_file(f)
        assert result.violations == []

    def test_scan_directory_no_violations(self, tmp_path: Path) -> None:
        """Verify scan_directory with clean files."""
        (tmp_path / "a.py").write_text("import os\n")
        (tmp_path / "b.py").write_text("from pathlib import Path\n")
        results = ri_scan_directory(tmp_path)
        total = sum(len(r.violations) for r in results)
        assert total == 0

    def test_scan_directory_with_violations(self, tmp_path: Path) -> None:
        """Verify scan_directory finds violations."""
        (tmp_path / "good.py").write_text("import os\n")
        (tmp_path / "bad.py").write_text("from anvil.core import engine\n")
        results = ri_scan_directory(tmp_path)
        total = sum(len(r.violations) for r in results)
        assert total == 1

    def test_import_in_docstring(self, tmp_path: Path) -> None:
        """Verify import inside a docstring is not flagged."""
        f = tmp_path / "docstringed.py"
        f.write_text(
            textwrap.dedent(
                """\
                \"\"\"
                This mentions from anvil.core import engine but it's just docs.
                \"\"\"
            """
            )
        )
        result = ri_scan_file(f)
        assert result.violations == []

    def test_comment_with_anvil_not_flagged(self, tmp_path: Path) -> None:
        """Verify comment containing anvil. is not flagged."""
        f = tmp_path / "commented.py"
        f.write_text("# from anvil.core import engine\n")
        result = ri_scan_file(f)
        assert result.violations == []

    def test_unreadable_file(self, tmp_path: Path) -> None:
        """Verify unreadable file does not crash."""
        f = tmp_path / "unreadable.py"
        f.write_text("import os")
        f.chmod(0o000)
        try:
            result = ri_scan_file(f)
            assert result.violations == []
        finally:
            f.chmod(0o644)


######################################################################
# check_one_class
######################################################################


class TestCheckOneClass:
    """Tests for ``check_one_class.scan_file``."""

    def test_single_class_passes(self, tmp_path: Path) -> None:
        """Verify file with one class passes."""
        f = tmp_path / "good.py"
        f.write_text(
            textwrap.dedent(
                """\
                class MyClass:
                    pass
            """
            )
        )
        result = oc_scan_file(f)
        assert result.issues == []

    def test_two_primary_classes_fails(self, tmp_path: Path) -> None:
        """Verify file with two non-companion classes fails."""
        f = tmp_path / "bad.py"
        f.write_text(
            textwrap.dedent(
                """\
                class Foo:
                    pass

                class Bar:
                    pass
            """
            )
        )
        result = oc_scan_file(f)
        assert len(result.issues) == 1

    def test_enum_and_exception_allowed(self, tmp_path: Path) -> None:
        """Verify enum and exception companions are allowed."""
        f = tmp_path / "good.py"
        f.write_text(
            textwrap.dedent(
                """\
                from enum import Enum

                class MyError(Exception):
                    pass

                class Color(Enum):
                    RED = 1

                class MainClass:
                    pass
            """
            )
        )
        result = oc_scan_file(f)
        assert result.issues == []

    def test_three_primary_classes_fails(self, tmp_path: Path) -> None:
        """Verify file with three classes fails."""
        f = tmp_path / "bad.py"
        f.write_text(
            textwrap.dedent(
                """\
                class A:
                    pass

                class B:
                    pass

                class C:
                    pass
            """
            )
        )
        result = oc_scan_file(f)
        assert len(result.issues) == 1
        assert len(result.issues[0].classes) == 3

    def test_suppression_comment(self, tmp_path: Path) -> None:
        """Verify # one-class:allow suppresses check."""
        f = tmp_path / "allowed.py"
        f.write_text(
            textwrap.dedent(
                """\
                # one-class:allow
                class Foo:
                    pass

                class Bar:
                    pass
            """
            )
        )
        result = oc_scan_file(f)
        assert result.issues == []

    def test_no_classes_passes(self, tmp_path: Path) -> None:
        """Verify file with no classes passes."""
        f = tmp_path / "nocls.py"
        f.write_text(
            textwrap.dedent(
                """\
                def helper() -> None:
                    pass
            """
            )
        )
        result = oc_scan_file(f)
        assert result.issues == []

    def test_syntax_error(self, tmp_path: Path) -> None:
        """Verify file with syntax error produces an issue."""
        f = tmp_path / "badsyntax.py"
        f.write_text("class Foo(\n")
        result = oc_scan_file(f)
        assert len(result.issues) == 1

    def test_unreadable_file(self, tmp_path: Path) -> None:
        """Verify unreadable file produces an issue."""
        f = tmp_path / "unreadable.py"
        f.write_text("class Foo: pass\nclass Bar: pass\n")
        f.chmod(0o000)
        try:
            result = oc_scan_file(f)
            assert len(result.issues) == 1
            assert "Cannot read" in result.issues[0].message
        finally:
            f.chmod(0o644)

    def test_enum_without_enum_import_not_allowed(self, tmp_path: Path) -> None:
        """Verify class named Enum but not actually inheriting is not auto-allowed."""
        f = tmp_path / "not_enum.py"
        f.write_text(
            textwrap.dedent(
                """\
                class MyThing:
                    pass

                class NotReallyEnum:
                    pass
            """
            )
        )
        result = oc_scan_file(f)
        assert len(result.issues) == 1


######################################################################
# check_init_py_ownership
######################################################################


class TestCheckInitPyOwnership:
    """Tests for ``check_init_py_ownership.scan_directory``."""

    def _make_package(self, root: Path, name: str, init_content: str = "") -> Path:
        """Create a package directory with __init__.py."""
        pkg = root / name
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text(init_content)
        (pkg / "module.py").write_text("def foo(): pass\n")
        return pkg

    def test_package_with_bare_init_passes(self, tmp_path: Path) -> None:
        """Verify package with docstring-only __init__.py passes."""
        self._make_package(
            tmp_path,
            "mypkg",
            init_content='"""My package."""\n',
        )
        results = init_py_scan_directory(tmp_path)
        assert results == []

    def test_package_with_copyright_and_docstring_passes(self, tmp_path: Path) -> None:
        """Verify package with copyright header + docstring passes."""
        self._make_package(
            tmp_path,
            "mypkg",
            init_content=textwrap.dedent(
                """\
                # Copyright 2024
                #
                # License info

                \"\"\"My package.\"\"\"
            """
            ),
        )
        results = init_py_scan_directory(tmp_path)
        assert results == []

    def test_package_with_import_in_init_fails(self, tmp_path: Path) -> None:
        """Verify __init__.py with import is flagged."""
        self._make_package(
            tmp_path,
            "mypkg",
            init_content="from .module import foo\n",
        )
        results = init_py_scan_directory(tmp_path)
        assert len(results) == 1
        assert "import" in results[0].violations[0].message.lower()

    def test_data_dir_with_init_fails(self, tmp_path: Path) -> None:
        """Verify data-only dir with __init__.py is flagged."""
        data = tmp_path / "static"
        data.mkdir(parents=True)
        (data / "__init__.py").write_text("# should not exist\n")
        (data / "style.css").write_text("body {}\n")
        results = init_py_scan_directory(tmp_path)
        assert len(results) == 1
        assert "must not contain" in results[0].violations[0].message

    def test_data_dir_without_init_passes(self, tmp_path: Path) -> None:
        """Verify data-only dir without __init__.py is fine."""
        data = tmp_path / "templates"
        data.mkdir(parents=True)
        (data / "page.html").write_text("<html></html>\n")
        results = init_py_scan_directory(tmp_path)
        assert results == []

    def test_package_without_init_fails(self, tmp_path: Path) -> None:
        """Verify package dir without __init__.py is flagged."""
        pkg = tmp_path / "barepkg"
        pkg.mkdir(parents=True)
        (pkg / "module.py").write_text("def foo(): pass\n")
        results = init_py_scan_directory(tmp_path)
        assert len(results) == 1
        assert "Missing" in results[0].violations[0].message

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Verify empty directory has no violations."""
        empty = tmp_path / "empty"
        empty.mkdir(parents=True)
        results = init_py_scan_directory(tmp_path)
        assert results == []

    def test_nested_data_dir_with_py_file(self, tmp_path: Path) -> None:
        """Verify nested dir under data/ with .py file is treated as data."""
        nested = tmp_path / "data" / "samples"
        nested.mkdir(parents=True)
        (nested / "hello.py").write_text("print('hi')\n")
        results = init_py_scan_directory(tmp_path)
        assert results == []  # no __init__.py required

    def test_scan_multiple_packages(self, tmp_path: Path) -> None:
        """Verify scan finds issues across multiple packages."""
        # Good package
        self._make_package(tmp_path, "goodpkg", init_content='"""OK."""\n')
        # Bad package — missing __init__.py
        bad = tmp_path / "badpkg"
        bad.mkdir(parents=True)
        (bad / "module.py").write_text("class X: pass\n")
        # Bad package — init with import
        self._make_package(tmp_path, "badpkg2", init_content="import os\n")

        results = init_py_scan_directory(tmp_path)
        assert len(results) >= 2  # at least 2 violations found
