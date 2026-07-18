"""Verify backup restore/delete confirm modals and notification history modal.

Triggers a backup via the "Create Backup" button, then tests the restore
and delete confirmation modals — verifying they appear on click and can be
cancelled without performing destructive operations. Also tests the
notification history modal opening and closing.
"""

from __future__ import annotations

import pytest


@pytest.mark.usefixtures("_readiness_check")
class TestOperationsModals:
    """Browser e2e tests for operations page modals."""

    TIMEOUT = 15_000  # 15 seconds (general UI timeout for modals)
    BACKUP_TIMEOUT = 120_000  # 120 seconds (backups can be slow in Docker CI)

    @staticmethod
    def _cleanup_backups(seed_client) -> None:
        """Delete all backups via the API to clean up test artifacts.

        Parameters
        ----------
        seed_client
            HTTP client used to seed test data via API.
        """
        try:
            resp = seed_client.get("/v1/backup")
            if resp.status_code == 200:
                backups = resp.json()
                if isinstance(backups, list):
                    for b in backups:
                        bid = b.get("backup_id")
                        if bid:
                            seed_client.delete(f"/v1/backup/{bid}?confirm_last=true")
        except Exception:
            pass

    @staticmethod
    def _create_backup(page, base_url: str, timeout: int) -> None:
        """Create a backup via the UI and wait for completion.

        Parameters
        ----------
        page
            Playwright page instance.
        base_url
            Application base URL.
        timeout
            Max wait time for backup completion in milliseconds.
        """
        page.goto(f"{base_url}/v1/operations-page")
        page.wait_for_load_state("networkidle")

        # Click the Create Backup button
        page.click("#btn-backup-create")

        # Wait for the confirmation modal
        page.wait_for_selector(".modal-overlay", state="visible", timeout=5000)

        # Confirm the backup
        page.click("#modal-confirm")

        # Wait for the progress card to appear (SSE connected)
        page.wait_for_selector("#backup-progress", state="visible", timeout=timeout)

        # Wait for the backup to complete — progress card hidden,
        # backup table has rows
        page.wait_for_function(
            "() => {"
            '  var progress = document.getElementById("backup-progress");'
            '  var tbody = document.getElementById("backup-tbody");'
            "  if (!progress || !tbody) return false;"
            "  var style = window.getComputedStyle(progress);"
            '  return style.display === "none" && tbody.children.length > 0;'
            "}",
            timeout=timeout,
        )

    def test_backup_restore_confirm_modal(
        self,
        page,
        base_url: str,
        assert_no_console_errors,
        seed_client,
    ) -> None:
        """Create backup, click restore, verify RESTORE modal, cancel it.

        The restore is a destructive operation — this test clicks Cancel
        on the confirmation modal rather than confirming.
        """
        checker = assert_no_console_errors(page)
        self._create_backup(page, base_url, self.BACKUP_TIMEOUT)

        # Wait for UI to settle after backup completes
        page.wait_for_timeout(2000)

        # Click the restore button on the first backup table row
        page.click("button[data-backup-action='restore']")

        # Wait for the restore confirmation modal to appear
        page.wait_for_selector(".modal-overlay", state="visible", timeout=self.TIMEOUT)

        # Verify the modal includes a RESTORE-labelled confirm button
        confirm_btn = page.locator("#modal-confirm")
        assert (
            confirm_btn.is_visible()
        ), "Restore confirm button (#modal-confirm) should be visible"
        btn_label = (confirm_btn.text_content() or "").strip()
        assert (
            "RESTORE" in btn_label
        ), f"Expected 'RESTORE' in confirm button, got '{btn_label}'"

        # Cancel the restore (destructive — must NOT confirm)
        page.click("#modal-cancel")

        # Wait for the modal to be dismissed
        page.wait_for_selector(".modal-overlay", state="hidden", timeout=self.TIMEOUT)

        checker.assert_no_errors()
        self._cleanup_backups(seed_client)

    def test_backup_delete_confirm_modal(
        self,
        page,
        base_url: str,
        assert_no_console_errors,
        seed_client,
    ) -> None:
        """Create backup, click delete, verify confirm modal, cancel it.

        The delete is a destructive operation — this test clicks Cancel
        on the confirmation modal rather than confirming.
        """
        checker = assert_no_console_errors(page)
        self._create_backup(page, base_url, self.BACKUP_TIMEOUT)

        # Wait for UI to settle after backup completes
        page.wait_for_timeout(2000)

        # Click the delete button on the first backup table row
        page.click("button[data-backup-action='delete']")

        # Wait for the delete confirmation modal to appear
        page.wait_for_selector(".modal-overlay", state="visible", timeout=self.TIMEOUT)

        # Verify the modal includes a Delete-labelled confirm button
        confirm_btn = page.locator("#modal-confirm")
        assert (
            confirm_btn.is_visible()
        ), "Delete confirm button (#modal-confirm) should be visible"
        btn_label = (confirm_btn.text_content() or "").strip()
        assert (
            "Delete" in btn_label
        ), f"Expected 'Delete' in confirm button, got '{btn_label}'"

        # Cancel the delete (destructive — must NOT confirm)
        page.click("#modal-cancel")

        # Wait for the modal to be dismissed
        page.wait_for_selector(".modal-overlay", state="hidden", timeout=self.TIMEOUT)

        checker.assert_no_errors()
        self._cleanup_backups(seed_client)

    def test_notification_history_modal(
        self,
        page,
        base_url: str,
        assert_no_console_errors,
    ) -> None:
        """Open the notification history modal and close it."""
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}/v1/operations-page")
        page.wait_for_load_state("networkidle")

        # Click the bell icon to open notification history
        page.click("#btn-notification-history")

        # Verify the notification modal opens
        notif_modal = page.locator("#notification-modal")
        notif_modal.wait_for(state="visible", timeout=self.TIMEOUT)
        assert (
            notif_modal.is_visible()
        ), "Notification modal (#notification-modal) should be visible"

        # Verify the modal has a title and close button
        close_btn = page.locator("#notification-modal-close")
        assert (
            close_btn.is_visible()
        ), "Notification modal close button should be visible"

        title = page.locator("#notification-modal .modal-dialog__title")
        assert title.is_visible(), "Modal title should be visible"
        title_text = (title.text_content() or "").strip()
        assert (
            "Notification" in title_text
        ), f"Expected 'Notification' in modal title, got '{title_text}'"

        # Close the modal
        close_btn.click()

        # Verify the modal is hidden
        notif_modal.wait_for(state="hidden", timeout=self.TIMEOUT)
        assert (
            not notif_modal.is_visible()
        ), "Notification modal should be hidden after close"

        checker.assert_no_errors()
