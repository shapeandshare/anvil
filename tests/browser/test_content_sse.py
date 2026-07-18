"""Verify the content library page SSE streams (injection monitor).

Navigates to the content page and verifies the injection monitor SSE
auto-connects on page load (proving the SSE endpoint is wired).

Also verifies the mount points for composer, import, and locks render.
"""

from __future__ import annotations

import pytest

CONTENT_PAGE = "/v1/content-page"


@pytest.mark.usefixtures("_readiness_check")
class TestContentSse:
    """Browser e2e tests for content page SSE wiring."""

    TIMEOUT = 30_000  # 30 seconds (Docker CI can be slow)

    def test_content_page_loads(
        self,
        page,
        base_url: str,
        assert_no_console_errors,
    ) -> None:
        """Verify the content page renders without console errors."""
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}{CONTENT_PAGE}")
        # Content page has persistent SSE stream — use domcontentloaded
        page.wait_for_load_state("domcontentloaded")
        checker.assert_no_errors()

    def test_injection_monitor_sse_connects(
        self,
        page,
        base_url: str,
        assert_no_console_errors,
    ) -> None:
        """Verify injection monitor SSE indicator renders with a state class."""
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}{CONTENT_PAGE}")
        # Content page has persistent SSE stream — use domcontentloaded
        page.wait_for_load_state("domcontentloaded")

        # Wait for the injection state indicator to be visible
        state_el = page.locator("#injection-state")
        state_el.wait_for(state="visible", timeout=self.TIMEOUT)

        # Verify it has a connection-state class (cs-idle, cs-streaming, etc.)
        class_attr = state_el.get_attribute("class") or ""
        assert "cs-" in class_attr, (
            f"Expected injection-state to have a cs-* class, " f"got: {class_attr!r}"
        )

        # Verify the sessions container rendered
        sessions = page.locator("#injection-sessions")
        assert sessions.count() > 0, "#injection-sessions should be present"

        checker.assert_no_errors()

    def test_injection_monitor_section_renders(
        self,
        page,
        base_url: str,
        assert_no_console_errors,
    ) -> None:
        """Verify the injection monitor section header and badge render."""
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}{CONTENT_PAGE}")
        # Content page has persistent SSE stream — use domcontentloaded
        page.wait_for_load_state("domcontentloaded")

        # Verify the section header is visible
        section = page.locator("text=Injection Monitor").first
        section.wait_for(state="visible", timeout=self.TIMEOUT)

        # Verify the badge element exists
        badge = page.locator("#injection-badge")
        assert badge.count() > 0, "#injection-badge should be present"

        # Verify mount points exist
        for mount_id in ("#composer-mount", "#import-mount", "#locks-mount"):
            mount = page.locator(mount_id)
            assert mount.count() > 0, f"{mount_id} should be present"

        checker.assert_no_errors()
