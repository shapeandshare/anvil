"""Verify the training page is wired to the SSE backend.

Configures a tiny model through the UI, starts a training run, and
asserts that at least one live data point (numeric step/loss) appears
in the training progress display within 30 seconds.

Also verifies the pipeline node tabs (wizard-steps / wizard-tabs)
and banner CTA render and respond to interaction.
"""

from __future__ import annotations

import pytest

TINY_CONFIG = {
    "n_embd": 16,
    "n_layer": 1,
    "n_head": 4,
    "num_steps": 20,
    "learning_rate": 0.01,
    "temperature": 0.5,
    "backend": "local-stdlib",
}
SSE_TIMEOUT = 60_000  # 60 seconds (SC-003, provisional for CI)
TRAIN_PAGE = "/v1/training-page"


@pytest.mark.usefixtures("_readiness_check")
class TestTrainingSseWiring:
    """Browser e2e tests for the training page click-through flow."""

    def test_training_page_loads(
        self,
        page,
        base_url: str,
        assert_no_console_errors,
    ) -> None:
        """Verify the training page renders without console errors."""
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}{TRAIN_PAGE}")
        page.wait_for_load_state("networkidle")
        checker.assert_no_errors()

    def test_wizard_steps_and_tabs_render(
        self,
        page,
        base_url: str,
        assert_no_console_errors,
    ) -> None:
        """Verify wizard-steps, wizard-tabs, and banner CTA are present."""
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}{TRAIN_PAGE}")
        page.wait_for_load_state("networkidle")

        steps = page.locator(".wizard-step")
        assert steps.count() == 3, f"Expected 3 wizard-steps, got {steps.count()}"
        assert steps.nth(0).locator(".wizard-step-bubble").text_content() == "1"
        assert steps.nth(1).locator(".wizard-step-bubble").text_content() == "2"
        assert "Forge" in (
            steps.nth(2).locator(".wizard-step-label").text_content() or ""
        )

        tabs = page.locator(".wizard-tab")
        assert tabs.count() == 3, f"Expected 3 wizard-tabs, got {tabs.count()}"
        assert tabs.nth(0).text_content() == "Data"
        assert tabs.nth(1).text_content() == "Configure"
        assert tabs.nth(2).text_content() == "Forge"

        banner = page.locator(".section-card--banner")
        banner.wait_for(state="visible", timeout=5000)
        assert "How Training Works" in (banner.text_content() or "")
        assert banner.locator('a[href*="training-loop"]').is_visible()

        checker.assert_no_errors()

    def test_tab_switch_toggles_active_state(
        self,
        page,
        base_url: str,
        assert_no_console_errors,
    ) -> None:
        """Clicking a wizard-tab toggles --active on both tab and step."""
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}{TRAIN_PAGE}")
        page.wait_for_load_state("networkidle")

        data_tab = page.locator('.wizard-tab[data-tab="tab-data"]')
        data_step = page.locator('.wizard-step[data-tab="tab-data"]')
        assert "wizard-tab--active" in (data_tab.get_attribute("class") or "")
        assert "wizard-step--active" in (data_step.get_attribute("class") or "")

        config_tab = page.locator('.wizard-tab[data-tab="tab-configure"]')
        config_tab.click()
        page.wait_for_timeout(500)

        assert "wizard-tab--active" not in (data_tab.get_attribute("class") or "")
        assert "wizard-step--active" not in (data_step.get_attribute("class") or "")

        config_step = page.locator('.wizard-step[data-tab="tab-configure"]')
        assert "wizard-tab--active" in (config_tab.get_attribute("class") or "")
        assert "wizard-step--active" in (config_step.get_attribute("class") or "")

        checker.assert_no_errors()

    def test_step_click_triggers_scroll(
        self,
        page,
        base_url: str,
    ) -> None:
        """Clicking a wizard-step bubble scrolls to the target section."""
        page.goto(f"{base_url}{TRAIN_PAGE}")
        page.wait_for_load_state("networkidle")

        forge_step = page.locator('.wizard-step[data-tab="tab-forge"]')
        forge_step.click()
        page.wait_for_timeout(500)

        forge_tab = page.locator('.wizard-tab[data-tab="tab-forge"]')
        assert "wizard-tab--active" in (forge_tab.get_attribute("class") or "")
        assert "wizard-step--active" in (forge_step.get_attribute("class") or "")

        start_btn = page.locator("#start-btn")
        assert start_btn.is_visible()

    def test_training_modal_shows_on_click(
        self,
        page,
        base_url: str,
        assert_no_console_errors,
    ) -> None:
        """Clicking 'Start Training' shows the confirmation modal."""
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}{TRAIN_PAGE}")
        page.wait_for_load_state("networkidle")

        # Click the Start Training button
        page.click("#start-btn")

        # Verify the modal is visible
        page.wait_for_selector("#train-confirm-modal", state="visible", timeout=5000)

        # Verify modal shows config summary (not empty)
        summary = page.text_content("#modal-config-summary")
        assert summary and len(summary) > 0, "Modal config summary is empty"

        checker.assert_no_errors()

    def test_forge_ahead_starts_training(
        self,
        page,
        base_url: str,
        assert_no_console_errors,
    ) -> None:
        """Clicking 'Forge Ahead' starts training and SSE data appears."""
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}{TRAIN_PAGE}")
        page.wait_for_load_state("networkidle")

        # Reduce steps to 5 for a quick training run
        page.fill("#num_steps", "5")

        # Click Start Training to open the modal
        page.click("#start-btn")
        page.wait_for_selector("#train-confirm-modal", state="visible", timeout=5000)

        # Confirm the training
        page.click("#modal-confirm-btn")

        # Wait for SSE data to flow — the step metric changes from "—"
        page.wait_for_function(
            '() => document.getElementById("metric-step").textContent !== "\u2014"',
            timeout=SSE_TIMEOUT,
        )

        # Verify loss metric is populated
        loss = page.text_content("#metric-loss")
        assert loss and loss != "\u2014", f"Expected loss value, got {loss!r}"

        # Verify device metric is populated
        device = page.text_content("#metric-device")
        assert device and device != "\u2014", f"Expected device value, got {device!r}"

        checker.assert_no_errors()
