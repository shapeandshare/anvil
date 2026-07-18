"""Verify the HuggingFace model browser page is wired to the backend.

Tests the search bar, curated model grid, and import jobs section
all render and respond correctly.
"""

from __future__ import annotations

import os

import pytest


@pytest.mark.usefixtures("_readiness_check")
class TestHfBrowserForms:
    """Smoke test: HF browser page → search, curated grid, import jobs."""

    TIMEOUT = 15_000  # 15 seconds

    def test_search_returns_results(
        self, page, base_url: str, assert_no_console_errors
    ) -> None:
        """Type a query, click search, verify results appear."""
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}/v1/hf-browser")
        page.wait_for_load_state("networkidle")

        page.fill("#hf-search", "llama")
        page.click("#hf-search-btn")
        page.wait_for_load_state("networkidle")

        # Results may be rendered hidden (no results found in Docker CI)
        page.locator("#hf-search-results").wait_for(
            state="attached", timeout=self.TIMEOUT
        )
        results_text = page.locator("#hf-search-results").text_content() or ""
        if len(results_text) == 0 and os.environ.get("CI"):
            pytest.skip("HF search unavailable in Docker CI")
        assert len(results_text) > 0, "Search results should not be empty"
        checker.assert_no_errors()

    def test_curated_grid_renders(
        self, page, base_url: str, assert_no_console_errors
    ) -> None:
        """Verify model cards are present with import buttons."""
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}/v1/hf-browser")
        page.wait_for_load_state("networkidle")

        cards = page.locator(".hf-card")
        assert cards.count() > 0, "Expected at least one curated model card"

        import_btns = page.locator(".hf-import-btn[data-hf-id]")
        assert (
            import_btns.count() > 0
        ), "Expected at least one import button on curated cards"
        checker.assert_no_errors()

    def test_import_jobs_section_renders(
        self, page, base_url: str, assert_no_console_errors
    ) -> None:
        """Verify the import jobs container is present."""
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}/v1/hf-browser")
        page.wait_for_load_state("networkidle")

        page.locator("#import-jobs-list").wait_for(
            state="visible", timeout=self.TIMEOUT
        )
        page.locator("#import-jobs-count").wait_for(
            state="visible", timeout=self.TIMEOUT
        )
        checker.assert_no_errors()
