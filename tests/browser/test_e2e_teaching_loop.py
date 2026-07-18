"""Playwright e2e test for the teaching loop end-to-end flow.

Creates a session, starts a training round, waits for SSE completion,
and inspects the round result.
"""

from __future__ import annotations

import pytest

TEACH_ROUTE = "/v1/teach"
SSE_TIMEOUT = 180_000  # 180 seconds (Docker CI latency)
TIMEOUT = 30_000


@pytest.mark.usefixtures("_readiness_check")
class TestTeachingLoopE2E:
    """End-to-end test for the teaching loop flow."""

    SSE_TIMEOUT = SSE_TIMEOUT
    TIMEOUT = TIMEOUT

    def test_full_teaching_loop(
        self,
        page,
        base_url: str,
        seed_client,
        assert_no_console_errors,
    ) -> None:
        """Create session, start round, wait for SSE training, inspect."""
        # Skip if teaching API is unavailable
        try:
            r = seed_client.get("/v1/teach/sessions")
            if r.status_code != 200:
                pytest.skip("Teaching API not available")
        except Exception:
            pytest.skip("Teaching API not reachable")
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}{TEACH_ROUTE}")
        page.wait_for_load_state("networkidle")

        # ── Phase 1: Create a new session ──────────────────────────────
        # The empty state guidance card is visible when no sessions exist
        page.locator("#empty-state-card").wait_for(state="visible", timeout=TIMEOUT)

        page.fill("#session-name", "E2E Test Session")
        # Submit the create-session form
        page.click("#create-session-form button[type='submit']")

        # Wait for toast confirmation that the session was created
        page.locator(".toast-success").wait_for(state="visible", timeout=TIMEOUT)

        # Wait for the session to be created and panels to appear
        page.locator("#active-session-panel").wait_for(state="visible", timeout=TIMEOUT)
        page.locator("#round-panel").wait_for(state="visible", timeout=TIMEOUT)

        # ── Phase 2: Verify session in sidebar ─────────────────────────
        page.locator("#session-list").wait_for(state="visible", timeout=TIMEOUT)
        session_list_text = page.locator("#session-list").text_content()
        assert session_list_text is not None
        assert (
            "E2E Test Session" in session_list_text
        ), f"Session name not found in sidebar. Got: {session_list_text!r}"

        # ── Phase 3: Click "Start New Round" CTA ───────────────────────
        page.locator("#start-round-cta").wait_for(state="visible", timeout=TIMEOUT)
        page.locator("#start-round-cta").click()
        # Allow the focus action to settle
        page.wait_for_timeout(300)

        # ── Phase 4: Fill round form ───────────────────────────────────
        page.fill("#round-examples", "hello world\nfoo bar\ntest data")
        page.fill("#round-steps", "5")

        # ── Phase 5: Start the round ───────────────────────────────────
        page.click("#start-round-btn")

        # Wait for training progress section to appear (SSE connected)
        page.locator("#training-progress").wait_for(state="visible", timeout=TIMEOUT)

        # ── Phase 6: Wait for SSE training to complete ─────────────────
        # The training-complete element becomes visible on the 'complete'
        # SSE event. This may take some time in CI.
        page.wait_for_selector(
            "#training-complete",
            state="visible",
            timeout=SSE_TIMEOUT,
        )

        # Verify the status text indicates completion
        status_text = page.locator("#training-status-text").text_content()
        assert (
            status_text == "Complete"
        ), f"Expected status 'Complete', got {status_text!r}"

        # Verify the completion message
        complete_text = page.locator("#training-complete").text_content()
        assert complete_text is not None
        assert (
            "Training finished successfully" in complete_text
        ), f"Unexpected completion text: {complete_text!r}"

        # Verify the progress bar reached 100%
        progress_bar = page.locator("#training-progress-bar")
        progress_style = progress_bar.get_attribute("style") or ""
        assert (
            "100%" in progress_style
        ), f"Expected progress bar at 100%, got style={progress_style!r}"

        # ── Phase 7: Inspect the round ─────────────────────────────────
        # The Inspect This Round button appears after SSE completion
        page.locator("#inspect-cta").wait_for(state="visible", timeout=TIMEOUT)
        page.locator("#inspect-cta").click()

        # The inspect panel is now visible with the experiment ID pre-filled
        page.locator("#inspect-panel").wait_for(state="visible", timeout=TIMEOUT)

        # Fill in a prompt and generate
        page.fill("#inspect-prompt", "hello")
        page.click("#inspect-panel button[type='submit']")

        # Wait for the inspect output to appear
        page.locator("#inspect-output").wait_for(state="visible", timeout=TIMEOUT)
        result_text = page.locator("#inspect-result-text").text_content()
        assert result_text is not None, "Expected inspect result text"
        assert len(result_text) > 0, "Expected non-empty inspect result"

        # ── Phase 8: Verify zero console errors ────────────────────────
        checker.assert_no_errors()
