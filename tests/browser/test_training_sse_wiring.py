"""Verify the training page is wired to the SSE backend.

Configures a tiny model through the UI, starts a training run, and
asserts that at least one live data point (numeric step/loss) appears
in the training progress display within 30 seconds.
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
SSE_TIMEOUT = 30_000  # 30 seconds (SC-003, provisional for CI)
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
