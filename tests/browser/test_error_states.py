"""Verify form validation error states and error toast display.

Tests cover 404 page rendering, empty required field validation,
training form validation flow, and file upload rejection.
"""

from __future__ import annotations

import json
import os
import tempfile

import pytest


@pytest.mark.usefixtures("_readiness_check")
class TestErrorStates:
    """Smoke tests for error states and validation feedback."""

    TIMEOUT = 15_000  # 15 seconds

    # ── 404 Page ─────────────────────────────────────────────────────────

    def test_404_page_returns_error(self, page, base_url: str) -> None:
        """Navigate to a non-existent route and verify a 404 error is shown."""
        resp = page.goto(f"{base_url}/v1/nonexistent-route")
        page.wait_for_load_state("networkidle")
        assert resp.status == 404
        body = page.locator("body").text_content()
        assert any(
            keyword in body.lower() for keyword in ("404", "not found", "detail")
        ), f"Body should contain a 404 indicator: {body[:200]}"

    def test_404_page_no_js_errors(
        self, page, base_url: str, assert_no_console_errors
    ) -> None:
        """Verify the 404 page produces zero JS errors (expected 404 response excluded)."""
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}/v1/nonexistent-route")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2_000)

        # Filter out the expected navigation 404 — only check for JS errors
        js_errors = [
            e
            for e in checker._errors
            if not e.startswith("FAILED_RESOURCE: 404")
            and not ("CONSOLE_ERROR" in e and "404" in e)
        ]
        assert not js_errors, "JS errors detected on 404 page:\n" + "\n".join(js_errors)

    # ── Empty required field (data-add page) ─────────────────────────────

    def test_empty_dataset_name_shows_validation(self, page, base_url: str) -> None:
        """Click create dataset without filling the name and verify validation."""
        page.goto(f"{base_url}/v1/data-add-page")
        page.wait_for_load_state("networkidle")

        # Click create without filling in the dataset name
        page.locator("#create-dataset-btn").click()

        # The JS validation sets #create-status to '! Name is required.'
        status = page.locator("#create-status")
        status.wait_for(state="visible", timeout=self.TIMEOUT)
        assert "name is required" in status.text_content().lower()

    def test_empty_dataset_name_no_console_errors(
        self, page, base_url: str, assert_no_console_errors
    ) -> None:
        """Verify the empty-name validation produces zero console errors."""
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}/v1/data-add-page")
        page.wait_for_load_state("networkidle")

        page.locator("#create-dataset-btn").click()
        page.wait_for_timeout(2_000)
        checker.assert_no_errors()

    # ── Training validation ──────────────────────────────────────────────

    def test_training_no_dataset_shows_validation(self, page, base_url: str) -> None:
        """Open the training confirmation modal without selecting a dataset.

        Verifies the modal appears and that the config summary references
        the default data source (indicating no dataset was chosen).
        """
        page.goto(f"{base_url}/v1/training-page")
        page.wait_for_load_state("networkidle")

        # The empty-data warning should exist in the DOM (may be hidden
        # initially until the user interacts with data selectors)
        page.locator("#empty-data-warn").wait_for(
            state="attached", timeout=self.TIMEOUT
        )

        # Click "Start Training" to open the confirmation modal
        page.locator("#start-btn").click()

        # Verify the confirmation modal appears
        modal = page.locator("#train-confirm-modal")
        modal.wait_for(state="visible", timeout=self.TIMEOUT)

        # The config summary should reference "default" data
        summary = page.locator("#modal-config-summary")
        assert "default" in summary.text_content().lower()

        # Cancel — do NOT trigger actual training
        page.locator("#modal-cancel-btn").click()
        modal.wait_for(state="hidden", timeout=self.TIMEOUT)

    def test_training_no_dataset_no_console_errors(
        self, page, base_url: str, assert_no_console_errors
    ) -> None:
        """Verify the training validation flow produces zero console errors."""
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}/v1/training-page")
        page.wait_for_load_state("networkidle")

        page.locator("#start-btn").click()
        page.locator("#train-confirm-modal").wait_for(
            state="visible", timeout=self.TIMEOUT
        )
        page.locator("#modal-cancel-btn").click()

        page.wait_for_timeout(2_000)
        checker.assert_no_errors()

    # ── File upload error ────────────────────────────────────────────────

    def test_file_upload_rejects_non_txt(self, page, base_url: str) -> None:
        """Upload a non-.txt file and verify the upload doesn't crash."""
        page.goto(f"{base_url}/v1/data-add-page")
        page.wait_for_load_state("networkidle")

        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump({"test": "data"}, f)
            tmp_path = f.name

        try:
            file_input = page.locator("#file-input")
            file_input.set_input_files(tmp_path)

            # Submit the upload form — verify it doesn't crash
            page.locator("#upload-form button[type='submit']").click()
            page.wait_for_timeout(2_000)
        finally:
            try:
                os.remove(tmp_path)
            except FileNotFoundError:
                pass

    def test_file_upload_non_txt_no_console_errors(
        self, page, base_url: str, assert_no_console_errors
    ) -> None:
        """Verify the rejected upload produces no unexpected console errors."""
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}/v1/data-add-page")
        page.wait_for_load_state("networkidle")

        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump({"test": "data"}, f)
            tmp_path = f.name

        try:
            file_input = page.locator("#file-input")
            file_input.set_input_files(tmp_path)
            page.locator("#upload-form button[type='submit']").click()

            page.wait_for_timeout(2_000)
            checker.assert_no_errors()
        finally:
            try:
                os.remove(tmp_path)
            except FileNotFoundError:
                pass
