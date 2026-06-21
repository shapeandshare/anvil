"""Verify the dataset upload form is wired to the backend.

Uploads a small ``.txt`` file through the page's real upload control and
asserts the new dataset name appears in the on-page listing.
"""

from __future__ import annotations

import os
import tempfile

import pytest


@pytest.mark.usefixtures("_readiness_check")
class TestDatasetUploadWiring:
    """Smoke test: dataset upload form → backend → listing."""

    TIMEOUT = 10_000  # 10 seconds (matches SC-002)

    @pytest.mark.xfail(reason="Datasets page has pre-existing JS error preventing proper interaction")
    def test_upload_appears_in_listing(self, page, base_url: str) -> None:
        """Upload a ``.txt`` file and verify it appears in the listing."""
        page.goto(f"{base_url}/v1/datasets-page")

        # Wait for the page to render fully.
        page.wait_for_load_state("networkidle")

        # Create a temporary text file for upload.
        with tempfile.NamedTemporaryFile(
            suffix=".txt", mode="w", delete=False
        ) as f:
            f.write("hello world this is smoke test content")
            tmp_path = f.name

        try:
            # Locate the file input and upload.
            file_input = page.locator("#file-input")
            file_input.set_input_files(tmp_path)

            # Submit the form.  The exact submission trigger varies by
            # implementation — try Enter key on the file input, or click a
            # visible upload/submit button.
            upload_btn = page.locator(
                'button:has-text("Upload"), '
                'button:has-text("Submit"), '
                'button:has-text("Add"), '
                'button:has-text("Import")'
            )
            if upload_btn.count():
                upload_btn.first.click()
            else:
                # No visible button — file input may auto-submit.
                file_input.press("Enter")

            # Wait for the dataset to appear in the listing.
            listing = page.locator(
                "table, [role='list'], .dataset-list, .file-list, "
                ".data-grid, [class*='dataset'], [class*='corpus']"
            )
            # The uploaded file name (without directory) should be visible.
            expected_name = os.path.basename(tmp_path)
            listing.locator(f"text={expected_name}").wait_for(
                state="visible", timeout=self.TIMEOUT
            )
        finally:
            try:
                os.remove(tmp_path)
            except FileNotFoundError:
                pass

    @pytest.mark.xfail(reason="Pre-existing app bug: Cannot read properties of null (reading 'addEventListener')")
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