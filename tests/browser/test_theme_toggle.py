"""Verify the theme toggle works and persists across page navigation.

The app uses a CSS custom-property-based theme system with a toggle
button in the navigation bar.  This test verifies clicking the toggle
changes the active theme and the preference persists on navigation.
"""

from __future__ import annotations

import pytest


@pytest.mark.usefixtures("_readiness_check")
class TestThemeToggle:
    """Browser tests: theme toggle interaction and persistence."""

    TIMEOUT = 15_000

    def test_theme_toggle_exists(self, page, base_url: str) -> None:
        """Verify the theme toggle button is visible in the nav bar."""
        page.goto(f"{base_url}/")
        page.wait_for_load_state("networkidle")
        toggle = page.locator("[data-theme-toggle], .theme-toggle, #theme-toggle")
        toggle.first.wait_for(state="visible", timeout=self.TIMEOUT)

    def test_theme_toggle_changes_mode(
        self,
        page,
        base_url: str,
        assert_no_console_errors,
    ) -> None:
        """Clicking the theme toggle toggles data-theme between dark and light."""
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}/")
        page.wait_for_load_state("networkidle")

        # Get the initial theme value
        initial_theme = page.evaluate(
            'document.documentElement.getAttribute("data-theme")'
        )
        assert initial_theme is not None, "data-theme should be set on <html>"

        # Click the theme toggle
        toggle = page.locator("#theme-toggle")
        toggle.wait_for(state="visible", timeout=self.TIMEOUT)
        toggle.click()
        page.wait_for_timeout(500)

        # Get the new theme value
        new_theme = page.evaluate('document.documentElement.getAttribute("data-theme")')

        # The toggle should flip between dark and light
        assert initial_theme != new_theme, (
            f"Expected data-theme to change from {initial_theme!r}, "
            f"but it stayed as {new_theme!r}"
        )
        assert new_theme in (
            "dark",
            "light",
        ), f"Expected data-theme to be 'dark' or 'light', got {new_theme!r}"
        checker.assert_no_errors()

    def test_theme_persists_across_navigation(
        self,
        page,
        base_url: str,
        assert_no_console_errors,
    ) -> None:
        """Theme preference persists when navigating to a different page."""
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}/")
        page.wait_for_load_state("networkidle")

        # Click theme toggle to change the theme
        toggle = page.locator("#theme-toggle")
        toggle.wait_for(state="visible", timeout=self.TIMEOUT)
        toggle.click()
        page.wait_for_timeout(500)

        new_theme = page.evaluate('document.documentElement.getAttribute("data-theme")')
        assert new_theme is not None, "data-theme should be set"

        # Navigate to a different page
        page.goto(f"{base_url}/v1/datasets-page")
        page.wait_for_load_state("networkidle")

        # Verify the theme preference persisted
        nav_theme = page.evaluate('document.documentElement.getAttribute("data-theme")')
        assert new_theme == nav_theme, (
            f"Expected data-theme {new_theme!r} to persist across navigation, "
            f"but got {nav_theme!r}"
        )
        checker.assert_no_errors()
