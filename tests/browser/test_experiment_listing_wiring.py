"""Verify a completed training run appears in the experiment listing.

After a training run completes, navigates to the experiments page and
asserts the run appears with its final loss value rendered.

Note: Full end-to-end verification (seeding a run via API and asserting
it appears in the list) is blocked by training-route discovery.  For
v1 the test checks the page renders without errors.
"""

from __future__ import annotations

import pytest


@pytest.mark.usefixtures("_readiness_check")
class TestExperimentListingWiring:
    """Smoke test: experiments page renders correctly."""

    def test_experiments_page_loads(
        self,
        page,
        base_url: str,
        assert_no_console_errors,
    ) -> None:
        """Verify the experiments page renders without errors."""
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}/v1/experiments-page")
        page.wait_for_load_state("networkidle")
        checker.assert_no_errors()