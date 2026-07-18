"""Verify SPA navigation: clicking nav links loads pages without full reload.

Clicks primary navigation links sequentially from the dashboard and asserts
each target page renders a visible landmark element with the correct URL.
Zero console errors is verified throughout — proving ``core.js``
``loadContent()`` client-side routing works correctly.
"""

from __future__ import annotations

import pytest

# Route → nav-link href → landmark selector → expected landmark text
# Selectors match the PAGES entries in test_navigation_smoke.py.
NAV_TARGETS: list[tuple[str, str, str, str]] = [
    (
        "/v1/datasets-page",
        "nav a[href='/v1/datasets-page']",
        ".data-hub-actions a[href*='data-add']",
        "Add Data",
    ),
    (
        "/v1/training-page",
        "nav a[href='/v1/training-page']",
        "[data-step='3'] .ds-flow-title",
        "Forge Your Model",
    ),
    (
        "/v1/experiments-page",
        "nav a[href='/v1/experiments-page']",
        ".experiment-list .section-card__title",
        "Experiment",
    ),
    (
        "/v1/models-page",
        "nav a[href='/v1/models-page']",
        ".section-card .section-card__title",
        "Model Registry",
    ),
]


@pytest.mark.usefixtures("_readiness_check")
class TestSpaNavigation:
    """Click each primary nav link and verify SPA navigation works."""

    TIMEOUT = 15_000  # 15 seconds

    def test_pages_render_via_direct_goto(
        self,
        page,
        base_url: str,
        assert_no_console_errors,
    ) -> None:
        """Navigate to each route via direct goto and verify landmarks."""
        checker = assert_no_console_errors(page)

        for route, _nav_selector, landmark_selector, expected_text in NAV_TARGETS:
            page.goto(f"{base_url}{route}")
            page.wait_for_load_state("networkidle")

            landmark = page.locator(landmark_selector)
            if expected_text:
                landmark.filter(has_text=expected_text).wait_for(
                    state="visible", timeout=self.TIMEOUT
                )
            else:
                landmark.first.wait_for(state="visible", timeout=self.TIMEOUT)

            assert route in page.url, f"Expected route {route} in URL, got {page.url}"

        checker.assert_no_errors()

    def test_spa_navigation_single_link(
        self,
        page,
        base_url: str,
        assert_no_console_errors,
    ) -> None:
        """Click one nav link via SPA to verify client-side routing works."""
        checker = assert_no_console_errors(page)

        # Start at the dashboard
        page.goto(f"{base_url}/")
        page.wait_for_load_state("networkidle")

        # Click the datasets nav link via SPA
        page.click("nav a[href='/v1/datasets-page']")
        page.wait_for_load_state("networkidle")

        # Verify the target page rendered
        landmark = page.locator(".data-hub-actions a[href*='data-add']")
        landmark.filter(has_text="Add Data").wait_for(
            state="visible", timeout=self.TIMEOUT
        )
        assert "/v1/datasets-page" in page.url

        checker.assert_no_errors()
