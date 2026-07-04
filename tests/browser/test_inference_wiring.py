"""Verify the inference playground page renders correctly.

Navigates to the inference page and asserts the page loads without
console errors. Full end-to-end inference verification (model selection
→ generation) requires the model-seeding API routes to be stabilised.
"""

from __future__ import annotations

import time

import httpx
import pytest

MODEL_POLL_RETRIES = 12
"""int: Number of times to poll for a demo model before giving up."""
MODEL_POLL_INTERVAL = 5
"""int: Seconds between model-ready polls."""


def _wait_for_inference_models(seed_client: httpx.Client) -> None:
    """Poll /v1/inference/models until returning a non-503 response.

    The demo model is warmed up in a background daemon thread during
    server startup. In Docker CI the warmup may not finish before the
    test navigates to the inference page, causing a transient 503.
    This helper waits for the model to become available.
    """
    for _ in range(MODEL_POLL_RETRIES):
        resp = seed_client.get("/v1/inference/models")
        if resp.status_code != 503:
            return
        time.sleep(MODEL_POLL_INTERVAL)


@pytest.mark.usefixtures("_readiness_check")
class TestInferenceWiring:
    """Smoke test: inference page renders without errors."""

    def test_inference_page_loads(
        self,
        page,
        base_url: str,
        assert_no_console_errors,
        seed_client: httpx.Client,
    ) -> None:
        """Verify the inference page loads without console errors."""
        _wait_for_inference_models(seed_client)
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}/v1/inference-page")
        page.wait_for_load_state("networkidle")
        checker.assert_no_errors()
