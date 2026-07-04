"""Playwright e2e tests for the teach page UX remediation."""

from __future__ import annotations

import pytest

TEACH_ROUTE = "/v1/teach"


@pytest.mark.usefixtures("_readiness_check")
class TestTeachUX:
    """UX tests for the teaching loop page."""

    TIMEOUT = 15_000

    # ── T013: US1 — Empty state guidance ────────────────────────────

    def test_empty_state_guidance_card_exists(
        self,
        page,
        base_url: str,
        assert_no_console_errors,
    ) -> None:
        """Guidance card is visible when no sessions exist."""
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}{TEACH_ROUTE}")
        page.wait_for_load_state("networkidle")

        card = page.locator("#empty-state-card")
        card.wait_for(state="visible", timeout=self.TIMEOUT)
        page.locator("#empty-state-card .section-card__title").wait_for(
            state="visible", timeout=self.TIMEOUT
        )
        create_btn = page.locator("#empty-state-card #empty-state-create-btn")
        create_btn.wait_for(state="visible", timeout=self.TIMEOUT)

        checker.assert_no_errors()

    def test_empty_state_hides_when_session_selected(
        self,
        page,
        base_url: str,
        assert_no_console_errors,
    ) -> None:
        """Guidance card hides after creating a session."""
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}{TEACH_ROUTE}")
        page.wait_for_load_state("networkidle")

        create_btn = page.locator("#empty-state-card #empty-state-create-btn")
        create_btn.wait_for(state="visible", timeout=self.TIMEOUT)
        create_btn.click()

        card = page.locator("#empty-state-card")
        card.wait_for(state="hidden", timeout=self.TIMEOUT)
        page.locator("#active-session-panel").wait_for(
            state="visible", timeout=self.TIMEOUT
        )

        checker.assert_no_errors()

    # ── T014: US2 — Flow continuity CTAs ────────────────────────────

    def test_active_session_shows_start_round_cta(
        self,
        page,
        base_url: str,
        assert_no_console_errors,
    ) -> None:
        """Active session panel shows 'Start New Round' CTA."""
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}{TEACH_ROUTE}")
        page.wait_for_load_state("networkidle")

        create_btn = page.locator("#empty-state-card #empty-state-create-btn")
        create_btn.wait_for(state="visible", timeout=self.TIMEOUT)
        create_btn.click()
        page.wait_for_timeout(500)

        start_round_cta = page.locator("#start-round-cta")
        start_round_cta.wait_for(state="visible", timeout=self.TIMEOUT)

        checker.assert_no_errors()

    def test_active_session_shows_delete_view_buttons(
        self,
        page,
        base_url: str,
        assert_no_console_errors,
    ) -> None:
        """Active session panel shows Delete and View Rounds buttons."""
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}{TEACH_ROUTE}")
        page.wait_for_load_state("networkidle")

        create_btn = page.locator("#empty-state-card #empty-state-create-btn")
        create_btn.wait_for(state="visible", timeout=self.TIMEOUT)
        create_btn.click()
        page.wait_for_timeout(500)

        delete_cta = page.locator("#delete-session-cta")
        delete_cta.wait_for(state="visible", timeout=self.TIMEOUT)
        view_rounds_cta = page.locator("#view-rounds-cta")
        view_rounds_cta.wait_for(state="visible", timeout=self.TIMEOUT)

        checker.assert_no_errors()

    # ── T015: US3 — Progressive disclosure ──────────────────────────

    def test_compare_panel_hidden_initially(
        self,
        page,
        base_url: str,
        assert_no_console_errors,
    ) -> None:
        """Compare panel is hidden or shows placeholder when few rounds."""
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}{TEACH_ROUTE}")
        page.wait_for_load_state("networkidle")

        compare_panel = page.locator("#compare-panel")
        compare_panel.wait_for(state="attached", timeout=self.TIMEOUT)

        compare_left = page.locator("#compare-left")
        is_hidden = not compare_left.is_visible()
        placeholder_visible = page.locator(
            "#compare-panel .compare-placeholder"
        ).is_visible()

        assert is_hidden or placeholder_visible, (
            "Compare panel should be hidden or show placeholder "
            "when fewer than 2 rounds exist"
        )

        checker.assert_no_errors()

    # ── T016: US4 — Visual polish ───────────────────────────────────

    def test_didyouknow_banner_present(
        self,
        page,
        base_url: str,
        assert_no_console_errors,
    ) -> None:
        """'Did You Know?' banner is present on the teach page."""
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}{TEACH_ROUTE}")
        page.wait_for_load_state("networkidle")

        banner = page.locator("#didyouknow-banner")
        banner.wait_for(state="attached", timeout=self.TIMEOUT)

        checker.assert_no_errors()

    def test_staggered_animations_present(
        self,
        page,
        base_url: str,
        assert_no_console_errors,
    ) -> None:
        """Section cards have --stagger-i attribute for entrance anim."""
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}{TEACH_ROUTE}")
        page.wait_for_load_state("networkidle")

        cards = page.locator(".section-card")
        count = cards.count()
        assert count > 0, "Expected at least one section-card on the page"

        stagger_found = False
        for i in range(count):
            style = cards.nth(i).get_attribute("style") or ""
            if "--stagger-i" in style:
                stagger_found = True
                break

        assert stagger_found, "No section-card with --stagger-i found"

        checker.assert_no_errors()

    def test_lesson_banner_cta_present(
        self,
        page,
        base_url: str,
        assert_no_console_errors,
    ) -> None:
        """Learning-lesson banner CTA is present on the teach page."""
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}{TEACH_ROUTE}")
        page.wait_for_load_state("networkidle")

        banner_cta = page.locator(".section-card--banner")
        banner_cta.wait_for(state="attached", timeout=self.TIMEOUT)

        checker.assert_no_errors()

    def test_sidebar_create_button_distinct(
        self,
        page,
        base_url: str,
        assert_no_console_errors,
    ) -> None:
        """Sidebar 'Create Session' button is visually distinct."""
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}{TEACH_ROUTE}")
        page.wait_for_load_state("networkidle")

        create_btn = page.locator(
            "#create-session-form button[type='submit']"
        )
        create_btn.wait_for(state="visible", timeout=self.TIMEOUT)

        class_attr = create_btn.get_attribute("class") or ""
        style_attr = create_btn.get_attribute("style") or ""

        has_distinction = (
            "btn-accent" in class_attr
            or "btn--forge" in class_attr
            or "box-shadow" in style_attr
            or "background" in style_attr
        )

        assert has_distinction, (
            "Create Session button should have visual distinction "
            "beyond plain btn-primary"
        )

        checker.assert_no_errors()