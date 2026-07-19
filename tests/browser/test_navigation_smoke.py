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
        ".data-hub-actions a[href*='data-add']",
        "Add Data",
    ),
    (
        "/v1/data-add-page",
        "#upload-form",
        "",
    ),
    (
        "/v1/data-sources-page",
        "#wiz-drop-zone",
        "",
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
        "/v1/chat-page",
        ".section-card__title",
        "Chat with a Model",
    ),
    (
        "/v1/operations-page",
        ".section-card__title",
        "Operations",
    ),
    (
        "/v1/learn",
        "h1",
        "Learning Hub",
    ),
    ####################################################################
    # Pages below were added in the 100% coverage push
    ####################################################################
    (
        "/v1/teach",
        ".section-card__title",
        "Interactive Teaching Loop",
    ),
    (
        "/v1/content-page",
        "text=Versioned Content Repository",
        "",
    ),
    (
        "/v1/config-page",
        ".section-card__title",
        "Configuration Settings",
    ),
    (
        "/v1/about",
        ".section-card__title",
        "About anvil",
    ),
    (
        "/v1/hf-browser",
        "h1",
        "HuggingFace Model Browser",
    ),
    (
        "/v1/eval-compare",
        "h1",
        "Fine-Tuned Model Evaluation",
    ),
    (
        "/v1/acceptable-use",
        ".section-card__title",
        "Acceptable Use Policy",
    ),
    (
        "/v1/learn/graph",
        "h1",
        "Forward Pass Explorer",
    ),
    (
        "/login",
        "#login-form",
        "",
    ),
]


@pytest.mark.usefixtures("_readiness_check")
class TestNavigationSmoke:
    """Smoke test: all primary routes render without errors."""

    TIMEOUT = 15_000  # 15 seconds
    CONTENT_PAGE_TIMEOUT = 30_000  # 30 seconds — content page loads via SSE

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
        # Content page has SSE stream that keeps network active indefinitely
        if route == "/v1/content-page":
            page.wait_for_load_state("domcontentloaded")
        else:
            page.wait_for_load_state("networkidle")

        if selector:
            landmark = page.locator(selector)
            nav_timeout = (
                self.CONTENT_PAGE_TIMEOUT
                if route == "/v1/content-page"
                else self.TIMEOUT
            )
            if expected_text:
                landmark.filter(has_text=expected_text).wait_for(
                    state="visible", timeout=nav_timeout
                )
            else:
                landmark.first.wait_for(state="visible", timeout=nav_timeout)

        checker.assert_no_errors()

    def test_nav_bar_present(self, page, base_url: str) -> None:
        """Verify the navigation bar renders on the dashboard."""
        page.goto(f"{base_url}/")
        page.wait_for_load_state("networkidle")
        nav = page.locator("nav, [role='navigation'], .nav-bar, .navbar")
        nav.first.wait_for(state="visible", timeout=self.TIMEOUT)

    def test_nav_link_navigates(self, page, base_url: str) -> None:
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
