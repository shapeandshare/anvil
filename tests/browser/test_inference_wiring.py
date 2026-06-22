"""Verify the inference playground page renders correctly.

Navigates to the inference page and asserts the page loads without
console errors. Full end-to-end inference verification (model selection
→ generation) requires the model-seeding API routes to be stabilised.
"""

from __future__ import annotations

import pytest


@pytest.mark.usefixtures("_readiness_check")
class TestInferenceWiring:
    """Smoke test: inference page renders without errors."""

    def test_inference_page_loads(
        self,
        page,
        base_url: str,
        assert_no_console_errors,
    ) -> None:
        """Verify the inference page loads without console errors."""
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}/v1/inference-page")
        page.wait_for_load_state("networkidle")
        checker.assert_no_errors()
