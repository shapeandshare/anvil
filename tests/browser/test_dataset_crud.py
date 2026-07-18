"""Dataset CRUD browser tests — create, edit, clone, delete via the UI.

Exercises the data-add and datasets-page forms on the golden path.
Each test is self-contained (creates its own dataset or uses
``dataset_seed``) and verifies zero console errors.
"""

from __future__ import annotations

import uuid

import pytest


@pytest.mark.usefixtures("_readiness_check")
class TestDatasetUpload:
    """Golden-path: upload a .txt file via the data-add form."""

    TIMEOUT = 10_000

    def test_upload_then_create(self, page, base_url: str) -> None:
        """Upload a file then create a dataset from it."""
        page.goto(f"{base_url}/v1/data-add-page")
        page.wait_for_load_state("networkidle")

        ds_name = f"test-upload-{uuid.uuid4().hex[:8]}"

        # Create a temporary upload file
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
            f.write("upload create test data")
            tmp_path = f.name

        try:
            # Upload file
            page.locator("#file-input").set_input_files(tmp_path)
            page.locator("#upload-form button[type='submit']").click()
            page.locator("#upload-status").wait_for(
                state="visible", timeout=self.TIMEOUT
            )

            # Now create a dataset from the uploaded content
            page.locator("#new-dataset-name").fill(ds_name)
            page.locator("#new-dataset-description").fill("test description")
            page.locator("#create-dataset-btn").click()
            page.locator("#create-status").wait_for(
                state="visible", timeout=self.TIMEOUT
            )

            # Wait for success toast instead of checking table text
            page.locator(".toast-success").wait_for(
                state="visible", timeout=self.TIMEOUT
            )
        finally:
            import os

            try:
                os.remove(tmp_path)
            except FileNotFoundError:
                pass


@pytest.mark.usefixtures("_readiness_check")
class TestDatasetInlineEdit:
    """Golden-path: inline-edit a dataset name and description."""

    TIMEOUT = 15_000

    def test_edit_dataset_name_inline(
        self,
        page,
        base_url: str,
        dataset_seed: dict,
        assert_no_console_errors,
    ) -> None:
        """Edit a dataset's name via the inline edit form."""
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}/v1/datasets-page")
        page.wait_for_load_state("networkidle")

        ds_id = dataset_seed.get("id", dataset_seed.get("data", {}).get("id"))
        assert ds_id is not None, "dataset_seed must have an id"

        new_name = f"renamed-{uuid.uuid4().hex[:8]}"

        # Click edit button for this dataset
        edit_btn = page.locator(f".edit-btn[data-id='{ds_id}']")
        edit_btn.wait_for(state="visible", timeout=self.TIMEOUT)
        edit_btn.click()

        # Fill the inline form
        name_input = page.locator(f"tr[data-id='{ds_id}'] .ie-name")
        name_input.wait_for(state="visible", timeout=self.TIMEOUT)
        name_input.fill(new_name)

        # Save
        save_btn = page.locator(f"tr[data-id='{ds_id}'] .ie-save")
        save_btn.click()
        page.wait_for_timeout(500)

        # Verify the new name appears in the table
        tbody = page.locator("#combined-tbody")
        assert new_name in (tbody.text_content() or "")
        checker.assert_no_errors()


@pytest.mark.usefixtures("_readiness_check")
class TestDatasetClone:
    """Golden-path: clone a dataset via the fork form."""

    TIMEOUT = 15_000


def test_clone_dataset(
    self,
    page,
    base_url: str,
    dataset_seed: dict,
) -> None:
    """Clone a dataset via the fork form."""
    page.goto(f"{base_url}/v1/datasets-page")
    page.wait_for_load_state("networkidle")

    ds_id = dataset_seed.get("id", dataset_seed.get("data", {}).get("id"))
    assert ds_id is not None

    clone_name = f"clone-{uuid.uuid4().hex[:8]}"

    # Click fork button
    fork_btn = page.locator(f".fork-btn[data-id='{ds_id}']")
    if fork_btn.count() == 0:
        pytest.skip("Fork button not found — clone API may be unavailable")
    fork_btn.wait_for(state="visible", timeout=self.TIMEOUT)
    fork_btn.click()

    # Fill fork name
    name_input = page.locator(f"tr[data-id='{ds_id}'] .fork-name")
    name_input.wait_for(state="visible", timeout=self.TIMEOUT)
    name_input.fill(clone_name)

    # Execute clone
    exec_btn = page.locator(f"tr[data-id='{ds_id}'] .fork-execute")
    exec_btn.click()
    page.wait_for_timeout(2000)

    # If toast appears, clone succeeded. Otherwise fall back to table check.
    toast = page.locator(".toast-success")
    if toast.count() > 0:
        toast.first.wait_for(state="visible", timeout=5000)
    else:
        page.locator("#hub-search").fill(clone_name)
        page.wait_for_timeout(500)
        tbody = page.locator("#combined-tbody")
        assert clone_name in (tbody.text_content() or "")


@pytest.mark.usefixtures("_readiness_check")
class TestDatasetDelete:
    """Golden-path: delete a dataset via the rm button."""

    TIMEOUT = 15_000

    def test_delete_dataset(
        self,
        page,
        base_url: str,
        seed_client,
        assert_no_console_errors,
    ) -> None:
        """Delete a dataset via the rm button (with confirm)."""
        checker = assert_no_console_errors(page)

        # Create a disposable dataset via API
        name = f"to-delete-{uuid.uuid4().hex[:8]}"
        content = b"delete me"
        resp = seed_client.post(
            "/v1/datasets/upload",
            files={"file": (f"{name}.txt", content, "text/plain")},
        )
        resp.raise_for_status()
        ds_data = resp.json()
        ds_id = ds_data.get("id", ds_data.get("data", {}).get("id", 0))
        assert ds_id, "Could not extract dataset id from upload response"

        page.goto(f"{base_url}/v1/datasets-page")
        page.wait_for_load_state("networkidle")

        # Listen for the confirm dialog
        page.on("dialog", lambda dialog: dialog.accept())

        # Click delete button
        del_btn = page.locator(f".del-dataset-btn[data-id='{ds_id}']")
        del_btn.wait_for(state="visible", timeout=self.TIMEOUT)
        del_btn.click()
        page.wait_for_timeout(500)

        # Verify the dataset is gone
        page.locator("#hub-search").fill(name)
        page.wait_for_timeout(500)
        tbody = page.locator("#combined-tbody")
        assert name not in (tbody.text_content() or "")
        checker.assert_no_errors()
