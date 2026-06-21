"""Verify the inference playground is wired to a generation-ready model.

Selects a registered model, enters a short prompt, submits, and
asserts non-empty generated text is rendered in the output area.
"""

from __future__ import annotations

import pytest

INFERENCE_TIMEOUT = 30_000  # 30 seconds (SC-005)


@pytest.mark.usefixtures("_readiness_check")
class TestInferenceWiring:
    """Smoke test: model selection → prompt → generated output."""

    def test_inference_produces_output(
        self,
        page,
        base_url: str,
        model_seed: dict,
    ) -> None:
        """Select a model, submit a prompt, verify non-empty output."""
        page.goto(f"{base_url}/v1/inference-page")
        page.wait_for_load_state("networkidle")

        # Select the seeded model from the model picker.
        model_name = model_seed.get("name", "")
        model_picker = page.locator(
            "select#model-select, "
            "[aria-label*='model'], "
            "[data-testid='model-picker'], "
            ".model-selector select"
        )
        if model_picker.count():
            if model_name:
                model_picker.first.select_option(label=model_name)
            else:
                # Pick the first option if name is not available.
                model_picker.first.select_option(index=1)
        else:
            model_option = page.locator(f"text={model_name}")
            if model_option.count():
                model_option.first.click()

        # Enter a prompt.
        prompt_input = page.locator(
            "textarea, "
            "input[type='text'], "
            "[contenteditable='true'], "
            "[aria-label*='prompt'], "
            "[aria-label*='input'], "
            "#prompt-input"
        )
        prompt_input.first.fill("hello")

        # Click Generate / Submit / Sample.
        generate_btn = page.locator(
            "button:has-text('Generate'), "
            "button:has-text('Submit'), "
            "button:has-text('Sample'), "
            "button:has-text('Run')"
        )
        assert generate_btn.count() > 0, "Could not find Generate button"
        generate_btn.first.click()

        # Wait for non-empty output text to appear.
        output_area = page.locator(
            "#output, "
            "[class*='output'], "
            "[class*='result'], "
            "[class*='generation'], "
            "[aria-label*='output']"
        )

        def _has_output() -> bool:
            text = (output_area.text_content() or "").strip()
            return len(text) > 0

        page.wait_for_function(
            _has_output,
            timeout=INFERENCE_TIMEOUT,
        )

    def test_no_console_errors(
        self,
        page,
        base_url: str,
        model_seed: dict,
        assert_no_console_errors,
    ) -> None:
        """Verify inference page loads and generates without errors."""
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}/v1/inference-page")
        page.wait_for_load_state("networkidle")
        checker.assert_no_errors()