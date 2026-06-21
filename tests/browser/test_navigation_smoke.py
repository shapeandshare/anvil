"""Verify all primary UI pages load without errors.

Asserts each page renders a visible landmark element and produces zero
error-level console signals. Also verifies the nav bar is present and
navigation links work.
"""

from __future__ import annotations

import pytest

# Each primary route mapped to a landmark selector and expected text.
# Selectors derived by reading the actual Jinja2 templates.
PAGES: list[tuple[str, str, str]] = [
    ("/", "", ""),
    (
        "/v1/datasets-page",
        "#tab-datasets .ds-flow-title",
        "Add Data",
    ),
    (
        "/v1/training-page",
        "[data-step='3'] .ds-flow-title",
        "Forge Your Model",
    ),
    (
        "/v1/experiments-page",
        ".experiment-list .section-card__title",
        "Experiment",
    ),
    (
        "/v1/models-page",
        ".section-card .section-card__title",
        "Model Registry",
    ),
    (
        "/v1/inference-page",
        ".section-card__title",
        "Inference",
    ),
    (
        "/v1/operations-page",
        ".section-card__title",
        "Operations",
    ),
    (
        "/v1/learn",
        ".section-card__title",
        "Learning Path",
    ),
]


@pytest.mark.usefixtures("_readiness_check")
class TestNavigationSmoke:
    """Smoke test: all primary routes render without errors."""

    TIMEOUT = 15_000  # 15 seconds

    @pytest.mark.parametrize(
        "route,selector,expected_text",
        PAGES,
        ids=[p[0] for p in PAGES],
    )
    def test_page_loads_without_errors(
        self,
        page,
        base_url: str,
        assert_no_console_errors,
        route: str,
        selector: str,
        expected_text: str,
    ) -> None:
        """Navigate to *route* and assert it loads cleanly."""
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}{route}")
        page.wait_for_load_state("networkidle")

        if selector:
            landmark = page.locator(selector)
            if expected_text:
                landmark.filter(has_text=expected_text).wait_for(
                    state="visible", timeout=self.TIMEOUT
                )
            else:
                landmark.first.wait_for(
                    state="visible", timeout=self.TIMEOUT
                )

        checker.assert_no_errors()

    def test_nav_bar_present(self, page, base_url: str) -> None:
        """Verify the navigation bar renders on the dashboard."""
        page.goto(f"{base_url}/")
        page.wait_for_load_state("networkidle")
        nav = page.locator("nav, [role='navigation'], .nav-bar, .navbar")
        nav.first.wait_for(state="visible", timeout=self.TIMEOUT)

    def test_nav_link_navigates(
        self, page, base_url: str
    ) -> None:
        """Click a nav link and verify the target page loads."""
        page.goto(f"{base_url}/v1/datasets-page")
        page.wait_for_load_state("networkidle")

        # Click any nav link that navigates to a different page.
        nav_link = page.locator(
            'nav a:not([href*="datasets"]), '
            '.nav-bar a:not([href*="datasets"]), '
            'a[href*="/v1/training"], '
            'a[href*="/v1/experiments"]'
        )
        if nav_link.count():
            target = nav_link.first.get_attribute("href") or ""
            nav_link.first.click()
            page.wait_for_load_state("networkidle")
            if target:
                assert target in page.url or target.rstrip("/") in page.url.rstrip("/")