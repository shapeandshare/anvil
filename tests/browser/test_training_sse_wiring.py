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
    """Smoke test: training start → live data point → completed state."""

    def test_training_produces_live_data_point(
        self,
        page,
        base_url: str,
        dataset_seed: dict,
        assert_no_console_errors,
    ) -> None:
        """Start training via the UI and verify ≥1 numeric data point."""
        checker = assert_no_console_errors(page)

        page.goto(f"{base_url}{TRAIN_PAGE}")
        page.wait_for_load_state("networkidle")

        # Select the seeded dataset.  The exact selector depends on the
        # page's dataset picker (dropdown/select/radio).  Try common
        # patterns — the implementer should refine based on training.html.
        dataset_picker = page.locator(
            "select#dataset-select, "
            "[aria-label*='dataset'], "
            "[data-testid='dataset-picker'], "
            ".dataset-selector select, "
            "#dataset-picker"
        )
        dataset_name = dataset_seed.get("_name", "")
        if dataset_picker.count():
            dataset_picker.first.select_option(label=dataset_name)
        else:
            # Fallback: picker may be a list of cards with dataset names.
            dataset_option = page.locator(f"text={dataset_name}")
            if dataset_option.count():
                dataset_option.first.click()

        # Set the tiny config.  Individual inputs may be present.
        for param_key, param_val in TINY_CONFIG.items():
            if isinstance(param_val, bool):
                continue
            input_el = page.locator(
                f"input[name='{param_key}'], "
                f"input[id*='{param_key}'], "
                f"[data-param='{param_key}'] input"
            )
            if input_el.count():
                input_el.first.fill(str(param_val))

        # Click the Start / Train button.
        start_btn = page.locator(
            "button:has-text('Start'), "
            "button:has-text('Train'), "
            "button:has-text('Forge'), "
            "button:has-text('Begin'), "
            "[type='submit']:has-text('Start')"
        )
        assert start_btn.count() > 0, "Could not find Start button"
        start_btn.first.click()

        # Wait for a numeric loss value to appear in #metric-loss.
        # We poll for a real number (not the default placeholder —).
        loss_locator = page.locator("#metric-loss")
        loss_locator.wait_for(state="visible", timeout=SSE_TIMEOUT)

        # Verify the text content is a real number (JS in browser).
        page.wait_for_function(
            "() => {"
            "  const el = document.querySelector('#metric-loss');"
            "  return el && /\\d+\\.\\d{4}/.test(el.textContent);"
            "}",
            timeout=SSE_TIMEOUT,
        )

        checker.assert_no_errors()

    def test_training_reaches_completed_state(
        self,
        page,
        base_url: str,
        dataset_seed: dict,
    ) -> None:
        """Start training and verify the UI shows a completed state."""
        page.goto(f"{base_url}{TRAIN_PAGE}")
        page.wait_for_load_state("networkidle")

        # Select dataset and start (same flow as above, simplified).
        dataset_picker = page.locator(
            "select#dataset-select, "
            "[aria-label*='dataset'], "
            ".dataset-selector select"
        )
        dataset_name = dataset_seed.get("_name", "")
        if dataset_picker.count():
            dataset_picker.first.select_option(label=dataset_name)

        start_btn = page.locator(
            "button:has-text('Start'), "
            "button:has-text('Train'), "
            "button:has-text('Forge')"
        )
        if start_btn.count():
            start_btn.first.click()

        # Wait for connection-state to become "done" or the "FINAL loss:"
        # banner to appear in the loss display (JS in browser).
        page.wait_for_function(
            "() => {"
            "  const state = document.querySelector('#connection-state');"
            "  if (state && state.textContent.trim() === 'done') return true;"
            "  const display = document.querySelector('#loss-display');"
            "  return display && display.textContent.includes('FINAL loss');"
            "}",
            timeout=SSE_TIMEOUT * 2,  # extra time for training to finish
        )

    def test_no_console_errors_during_training(
        self,
        page,
        base_url: str,
        dataset_seed: dict,
        assert_no_console_errors,
    ) -> None:
        """Start training and verify no console errors surface."""
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}{TRAIN_PAGE}")
        page.wait_for_load_state("networkidle")

        start_btn = page.locator(
            "button:has-text('Start'), "
            "button:has-text('Train'), "
            "button:has-text('Forge')"
        )
        if start_btn.count():
            start_btn.first.click()

        page.wait_for_timeout(5_000)  # let training run + surface errors
        checker.assert_no_errors()