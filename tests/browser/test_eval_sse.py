"""Verify the eval compare page renders with SSE-connected elements.

The eval compare page uses the SSESession utility to stream evaluation
progress. This test verifies the page renders the SSE-connected UI
elements without triggering a real evaluation run.
"""

from __future__ import annotations

import pytest


@pytest.mark.usefixtures("_readiness_check")
class TestEvalSse:
    """Browser tests: eval compare page SSE elements."""

    TIMEOUT = 15_000

    def test_eval_page_renders_sse_elements(
        self,
        page,
        base_url: str,
        assert_no_console_errors,
    ) -> None:
        """Verify the eval page renders SSE-connected status and progress elements."""
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}/v1/eval-compare")
        page.wait_for_load_state("networkidle")

        # Verify the core SSE-connected elements are present
        status_bar = page.locator("#eval-status")
        status_bar.wait_for(state="visible", timeout=self.TIMEOUT)

        status_text = page.locator("#status-text")
        status_text.wait_for(state="visible", timeout=self.TIMEOUT)

        progress_section = page.locator("#eval-progress")
        progress_section.wait_for(state="attached", timeout=self.TIMEOUT)

        progress_bar = page.locator("#progress-bar")
        progress_bar.wait_for(state="attached", timeout=self.TIMEOUT)

        metrics_section = page.locator("#metrics-section")
        metrics_section.wait_for(state="attached", timeout=self.TIMEOUT)

        samples_section = page.locator("#samples-section")
        samples_section.wait_for(state="attached", timeout=self.TIMEOUT)

        # Verify model name placeholders
        ft_name = page.locator("#ft-model-name")
        assert ft_name.text_content() == "\u2014"

        base_name = page.locator("#base-model-name")
        assert base_name.text_content() == "\u2014"

        checker.assert_no_errors()
