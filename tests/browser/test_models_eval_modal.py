"""Regression: native prompt()/alert() replaced with custom eval modal.

FIX #2 — The "Evaluate" flow (``.eval-btn`` click) previously used
``prompt()`` / ``alert()``. Replaced with a custom ``.modal-dialog``
containing two labeled inputs, inline validation, Cancel/Confirm buttons,
Escape-to-close, and focus management via ``showEvalModal``.

This test verifies:
- No native dialog fires when the eval button is clicked
- The custom modal appears with both inputs visible
- Invalid input shows inline error in ``#eval-base-id-error``
- Cancel dismisses the modal without navigation
- Escape key dismisses the modal
"""

from __future__ import annotations

import pytest


@pytest.mark.usefixtures("_readiness_check")
class TestModelsEvalModal:
    """Browser e2e tests for the Evaluate Model custom modal dialog."""

    TIMEOUT = 15_000

    def test_eval_modal_no_native_dialog(
        self,
        page,
        base_url: str,
        model_seed: dict,
        assert_no_console_errors,
    ) -> None:
        """Click eval button, verify no native prompt()/alert() fires."""
        checker = assert_no_console_errors(page)

        # Fail hard if any native browser dialog appears
        page.on("dialog", lambda dialog: pytest.fail(
            "Native dialog appeared: " + dialog.message
        ))

        page.goto(f"{base_url}/v1/models-page")
        page.wait_for_load_state("networkidle")

        # Wait for the models table to be populated
        page.locator("#models-tbody tr").first.wait_for(
            state="visible", timeout=self.TIMEOUT
        )

        # Click the first eval button
        eval_btn = page.locator(".eval-btn").first
        eval_btn.wait_for(state="visible", timeout=self.TIMEOUT)
        eval_btn.click()

        # Verify the custom modal overlay appears
        overlay = page.locator(".modal-overlay")
        overlay.wait_for(state="visible", timeout=self.TIMEOUT)

        # Verify modal title
        title = overlay.locator(".modal-dialog__title")
        assert title.is_visible(), "Modal title should be visible"
        title_text = (title.text_content() or "").strip()
        assert "Evaluate Model" in title_text, (
            f"Expected 'Evaluate Model' in modal title, got {title_text!r}"
        )

        # Verify both labeled inputs are visible
        base_id_input = overlay.locator("#eval-base-id")
        assert base_id_input.is_visible(), "Base Model ID input should be visible"

        dataset_input = overlay.locator("#eval-dataset")
        assert dataset_input.is_visible(), "Eval Dataset input should be visible"

        # Verify Cancel and Confirm buttons are present
        cancel_btn = overlay.locator("#eval-modal-cancel")
        assert cancel_btn.is_visible(), "Cancel button should be visible"

        confirm_btn = overlay.locator("#eval-modal-confirm")
        assert confirm_btn.is_visible(), "Confirm button should be visible"

        checker.assert_no_errors()

    def test_eval_modal_invalid_input_shows_error(
        self,
        page,
        base_url: str,
        model_seed: dict,
        assert_no_console_errors,
    ) -> None:
        """Enter invalid Base Model ID and verify inline error appears."""
        checker = assert_no_console_errors(page)

        page.on("dialog", lambda dialog: pytest.fail(
            "Native dialog appeared: " + dialog.message
        ))

        page.goto(f"{base_url}/v1/models-page")
        page.wait_for_load_state("networkidle")
        page.locator("#models-tbody tr").first.wait_for(
            state="visible", timeout=self.TIMEOUT
        )

        # Open the eval modal
        page.locator(".eval-btn").first.click()
        overlay = page.locator(".modal-overlay")
        overlay.wait_for(state="visible", timeout=self.TIMEOUT)

        # Fill invalid Base Model ID (non-numeric string)
        overlay.locator("#eval-base-id").fill("abc")
        overlay.locator("#eval-dataset").fill("my-eval-dataset")

        # Click Confirm
        overlay.locator("#eval-modal-confirm").click()

        # Verify inline error appears
        error_el = overlay.locator("#eval-base-id-error")
        error_el.wait_for(state="visible", timeout=5000)
        error_text = (error_el.text_content() or "").strip()
        assert error_text, "Error element should have text content"
        assert "invalid" in error_text.lower() or "valid" in error_text.lower(), (
            f"Expected validation error about invalid/valid model ID, "
            f"got {error_text!r}"
        )

        checker.assert_no_errors()

    def test_eval_modal_cancel_closes_modal(
        self,
        page,
        base_url: str,
        model_seed: dict,
        assert_no_console_errors,
    ) -> None:
        """Fill valid inputs, click Cancel, verify modal closes without navigation."""
        checker = assert_no_console_errors(page)

        page.on("dialog", lambda dialog: pytest.fail(
            "Native dialog appeared: " + dialog.message
        ))

        page.goto(f"{base_url}/v1/models-page")
        page.wait_for_load_state("networkidle")
        page.locator("#models-tbody tr").first.wait_for(
            state="visible", timeout=self.TIMEOUT
        )

        # Open the eval modal
        page.locator(".eval-btn").first.click()
        overlay = page.locator(".modal-overlay")
        overlay.wait_for(state="visible", timeout=self.TIMEOUT)

        # Fill valid inputs
        overlay.locator("#eval-base-id").fill("42")
        overlay.locator("#eval-dataset").fill("my-eval-dataset")

        # Click Cancel
        overlay.locator("#eval-modal-cancel").click()

        # Wait for the modal to close (250ms animation + buffer)
        page.wait_for_timeout(1000)
        overlay_count = page.locator(".modal-overlay").count()
        assert overlay_count == 0, (
            f"Modal should be closed after Cancel, "
            f"but found {overlay_count} overlay(s)"
        )

        # Verify we're still on the models page (no navigation to eval-compare)
        assert "models-page" in page.url, (
            f"Expected to stay on models-page after Cancel, "
            f"but URL is {page.url}"
        )

        checker.assert_no_errors()

    def test_eval_modal_escape_closes(
        self,
        page,
        base_url: str,
        model_seed: dict,
        assert_no_console_errors,
    ) -> None:
        """Open eval modal, press Escape, verify it closes."""
        checker = assert_no_console_errors(page)

        page.on("dialog", lambda dialog: pytest.fail(
            "Native dialog appeared: " + dialog.message
        ))

        page.goto(f"{base_url}/v1/models-page")
        page.wait_for_load_state("networkidle")
        page.locator("#models-tbody tr").first.wait_for(
            state="visible", timeout=self.TIMEOUT
        )

        # Open the eval modal
        page.locator(".eval-btn").first.click()
        overlay = page.locator(".modal-overlay")
        overlay.wait_for(state="visible", timeout=self.TIMEOUT)

        # Press Escape
        page.keyboard.press("Escape")

        # Wait for the modal to close (250ms animation + buffer)
        page.wait_for_timeout(1000)
        overlay_count = page.locator(".modal-overlay").count()
        assert overlay_count == 0, (
            f"Modal should be closed after Escape, "
            f"but found {overlay_count} overlay(s)"
        )

        checker.assert_no_errors()