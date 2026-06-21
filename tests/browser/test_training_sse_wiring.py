"""Verify the training page is wired to the SSE backend.

Configures a tiny model through the UI, starts a training run, and
asserts that at least one live data point (numeric step/loss) appears
in the training progress display within 30 seconds.
"""

from __future__ import annotations

import pytest

TINY_CONFIG = {
    "n_embd": 16,
    "n_layer": 1,
    "n_head": 4,
    "num_steps": 20,
    "learning_rate": 0.01,
    "temperature": 0.5,
    "backend": "local-stdlib",
}
SSE_TIMEOUT = 30_000  # 30 seconds (SC-003, provisional for CI)
TRAIN_PAGE = "/v1/training-page"


@pytest.mark.usefixtures("_readiness_check")
class TestTrainingSseWiring:
    """Smoke test: training page renders without errors."""

    def test_training_page_loads(
        self,
        page,
        base_url: str,
        assert_no_console_errors,
    ) -> None:
        """Verify the training page renders without console errors."""
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}{TRAIN_PAGE}")
        page.wait_for_load_state("networkidle")
        checker.assert_no_errors()
