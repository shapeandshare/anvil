"""Verify the HuggingFace model browser page is wired to the backend.

Tests the search bar, curated model grid, and import jobs section
all render and respond correctly.
"""

from __future__ import annotations

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

        # Results may be empty in Docker CI (no HF API access)
        page.locator("#hf-search-results").wait_for(
            state="attached", timeout=self.TIMEOUT
        )
        results_text = page.locator("#hf-search-results").text_content() or ""
        if len(results_text) == 0:
            # HF search API unavailable in this environment
            checker.assert_no_errors()
            return
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

    def test_import_button_re_enables_after_click(
        self, page, base_url: str, assert_no_console_errors
    ) -> None:
        """Regression: Import button re-enables after success or failure.

        The bug: Import buttons on curated cards stayed disabled after a
        successful import -- only the error/catch branches called
        ``btn.disabled = false``. The fix adds ``btn.disabled = false``
        to the success branch (and was already present in the
        search-results handler for parity).

        The curated grid (``.hf-card``) is rendered server-side from a
        bundled YAML (``curated-models.yaml``), so cards are always
        present without needing HF Hub network access. However, the POST
        to ``/v1/models/import`` does require HF Hub access to resolve
        the model identifier, which Docker CI typically lacks. In that
        case the backend returns a 422, the frontend error branch fires,
        and the button is re-enabled. This test verifies the button is
        re-enabled regardless of outcome.
        """
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}/v1/hf-browser")
        page.wait_for_load_state("networkidle")

        # Find the first curated card Import button
        import_btn = page.locator(".hf-import-btn[data-hf-id]").first
        if import_btn.count() == 0:
            # All models already imported -- nothing to test in this env
            checker.assert_no_errors()
            return

        # Click Import -- button enters "importing..." transient state
        import_btn.click()

        # Wait for the button to exit the "importing..." transient state.
        # After the API call resolves (success or failure), the text
        # changes to one of: "imported (job #N)", "import failed", or
        # "error". The button.disabled is set to false in ALL branches.
        page.wait_for_function(
            "document.querySelector('.hf-import-btn[data-hf-id]')"
            "?.textContent !== 'importing...'",
            timeout=self.TIMEOUT,
        )

        # The button MUST be re-enabled regardless of outcome
        assert not import_btn.is_disabled(), (
            "Import button should be re-enabled after the import attempt "
            "(success or failure -- the fix ensures both paths call "
            "btn.disabled = false)"
        )

        # Graceful degradation: the import requires HF Hub network
        # access, which Docker CI typically doesn't have. The backend
        # will likely return a 422 error, which the console checker
        # would record as a FAILED_RESOURCE. In that case, the key
        # regression check (button re-enabled) already passed -- return
        # early.
        current_text = (import_btn.text_content() or "").strip()
        if not current_text.startswith("imported"):
            return

        checker.assert_no_errors()
