# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for the HelpSection model and HELP_SECTIONS collection."""

import pytest
from pydantic import ValidationError

from anvil.api.v1.help_content import HELP_SECTIONS, HelpSection


class TestHelpSection:
    """HelpSection model validation tests."""

    def test_valid_section(self):
        """A well-formed HelpSection passes model validation."""
        section = HelpSection(
            anchor_id="test-section",
            title="Test Section",
            route="/v1/test-page",
            description="A test section.",
            content="<p>Some help content.</p>",
            related_lesson_keys=["faq", "glossary"],
        )
        assert section.anchor_id == "test-section"
        assert section.title == "Test Section"
        assert section.route == "/v1/test-page"
        assert section.description == "A test section."
        assert section.content == "<p>Some help content.</p>"
        assert section.related_lesson_keys == ["faq", "glossary"]

    def test_default_related_lessons(self):
        """related_lesson_keys defaults to empty list when omitted."""
        section = HelpSection(
            anchor_id="minimal",
            title="Minimal",
            route="/v1/minimal",
            description="Minimal section.",
            content="<p>Content</p>",
        )
        assert section.related_lesson_keys == []

    def test_empty_anchor_id_raises(self):
        """anchor_id must not be empty (Str constraint)."""
        with pytest.raises(ValidationError):
            HelpSection(
                anchor_id="",
                title="Bad",
                route="/v1/bad",
                description="Bad section.",
                content="<p>Content</p>",
            )


class TestHelpSections:
    """HELP_SECTIONS collection tests."""

    def test_all_sections_present(self):
        """HELP_SECTIONS contains exactly 7 workspace sections."""
        assert len(HELP_SECTIONS) == 7

    def test_sections_have_unique_anchor_ids(self):
        """Every section has a unique anchor_id."""
        ids = [s.anchor_id for s in HELP_SECTIONS]
        assert len(ids) == len(set(ids))

    def test_sections_have_required_fields(self):
        """Every section has non-empty anchor_id, title, route, description, content."""
        for section in HELP_SECTIONS:
            assert section.anchor_id, f"Missing anchor_id in {section.title}"
            assert section.title, "Missing title"
            assert section.route, f"Missing route in {section.title}"
            assert section.description, f"Missing description in {section.title}"
            assert section.content, f"Missing content in {section.title}"

    def test_anchor_ids_are_kebab_case(self):
        """All anchor_ids match lowercase kebab-case pattern."""
        import re

        for section in HELP_SECTIONS:
            assert re.match(
                r"^[a-z0-9-]+$", section.anchor_id
            ), f"Invalid anchor_id: {section.anchor_id}"

    def test_routes_start_with_slash(self):
        """Every route starts with /."""
        for section in HELP_SECTIONS:
            assert section.route.startswith(
                "/"
            ), f"Route does not start with /: {section.route}"

    def test_sections_include_training(self):
        """The Training Dashboard section is present."""
        assert any(
            s.anchor_id == "training" for s in HELP_SECTIONS
        ), "Missing training section"

    def test_sections_include_data(self):
        """The Data section is present."""
        assert any(s.anchor_id == "data" for s in HELP_SECTIONS), "Missing data section"

    def test_sections_include_content_library(self):
        """The Content Library section is present."""
        assert any(
            s.anchor_id == "content-library" for s in HELP_SECTIONS
        ), "Missing content-library section"
