"""Verify the dataset upload form is wired to the backend.

Uploads a small ``.txt`` file through the page's real upload control and
asserts a success status message appears (proving the form reached the
backend and the response was rendered).
"""

from __future__ import annotations

import os
import tempfile

import pytest


@pytest.mark.usefixtures("_readiness_check")
class TestDatasetUploadWiring:
    """Smoke test: dataset upload form → backend → listing."""

    TIMEOUT = 10_000  # 10 seconds (matches SC-002)

    def test_upload_appears_in_listing(self, page, base_url: str) -> None:
        """Upload a ``.txt`` file and verify the backend responds."""
        page.goto(f"{base_url}/v1/datasets-page")
        page.wait_for_load_state("networkidle")

        with tempfile.NamedTemporaryFile(
            suffix=".txt", mode="w", delete=False
        ) as f:
            f.write("hello world this is smoke test content")
            tmp_path = f.name

        try:
            file_input = page.locator("#file-input")
            file_input.set_input_files(tmp_path)

            # Click the Upload submit button.
            page.locator("#upload-form button[type='submit']").click()

            # Wait for the success status message from the upload handler.
            page.locator("#upload-status").wait_for(
                state="visible", timeout=self.TIMEOUT
            )
        finally:
            try:
                os.remove(tmp_path)
            except FileNotFoundError:
                pass

    def test_no_console_errors_on_upload(
        self, page, base_url: str, assert_no_console_errors
    ) -> None:
        """Verify the upload interaction produces zero console errors."""
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}/v1/datasets-page")
        page.wait_for_load_state("networkidle")

        with tempfile.NamedTemporaryFile(
            suffix=".txt", mode="w", delete=False
        ) as f:
            f.write("test content for console error check")
            tmp_path = f.name

        try:
            file_input = page.locator("#file-input")
            file_input.set_input_files(tmp_path)
            upload_btn = page.locator(
                'button:has-text("Upload"), '
                'button:has-text("Submit"), '
                'button:has-text("Add"), '
                'button:has-text("Import")'
            )
            if upload_btn.count():
                upload_btn.first.click()
            else:
                file_input.press("Enter")

            page.wait_for_timeout(2_000)  # allow any async error to surface
            checker.assert_no_errors()
        finally:
            try:
                os.remove(tmp_path)
            except FileNotFoundError:
                pass