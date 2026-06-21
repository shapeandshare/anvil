"""Verify a completed training run appears in the experiment listing.

After a training run completes, navigates to the experiments page and
asserts the run appears with its final loss value rendered.
"""

from __future__ import annotations

import pytest


@pytest.mark.usefixtures("_readiness_check")
class TestExperimentListingWiring:
    """Smoke test: completed run → experiment listing."""

    LISTING_TIMEOUT = 30_000  # 30 seconds for MLflow to surface the run

    def test_completed_run_appears_in_experiments(
        self,
        page,
        base_url: str,
        dataset_seed: dict,
    ) -> None:
        """Run training via API, then verify the run appears in the UI."""
        import httpx

        # Start a training run via API (fast seeding — the UI wiring is
        # about the listing page, not the training form).
        seed_client = httpx.Client(base_url=base_url, timeout=30.0)
        train_resp = seed_client.post(
            "/v1/training/start",
            json={
                "dataset_id": dataset_seed["id"],
                "name": "ui-smoke-test-run",
                "config": {
                    "n_embd": 16,
                    "n_layer": 1,
                    "n_head": 4,
                    "num_steps": 10,
                    "learning_rate": 0.01,
                    "temperature": 0.5,
                    "backend": "local-stdlib",
                },
            },
        )
        train_resp.raise_for_status()
        run_id = train_resp.json().get("run_id") or train_resp.json().get(
            "id"
        )

        # Wait for training completion via API poll.
        import time

        for _ in range(30):
            status_resp = seed_client.get(
                f"/v1/training/status/{run_id}"
            )
            if status_resp.status_code == 200:
                status_data = status_resp.json()
                if status_data.get("status") in (
                    "completed",
                    "done",
                    "finished",
                ):
                    break
            time.sleep(1)
        else:
            raise RuntimeError(
                f"Training run {run_id} did not complete in 30s"
            )

        # Navigate to the experiments page and assert the run appears.
        page.goto(f"{base_url}/v1/experiments-page")
        page.wait_for_load_state("networkidle")

        # The run should appear in the experiment list.  Poll for it
        # because the MLflow sidecar may surface it slightly after the
        # page loads.
        page.locator(
            f"text={run_id}, text='ui-smoke-test-run'"
        ).wait_for(state="visible", timeout=self.LISTING_TIMEOUT)

        # Verify a final loss value is rendered nearby.
        row = page.locator(f"text='ui-smoke-test-run'").locator("..")
        loss_cell = row.locator(
            "[class*='loss'], [class*='metric'], td:nth-child(2)"
        )
        loss_cell.wait_for(state="visible", timeout=5_000)

    def test_no_console_errors(
        self,
        page,
        base_url: str,
        dataset_seed: dict,
        assert_no_console_errors,
    ) -> None:
        """Verify the experiments page loads without console errors."""
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}/v1/experiments-page")
        page.wait_for_load_state("networkidle")
        checker.assert_no_errors()