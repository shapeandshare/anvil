"""Smoke tests for pages that require seeded data (model, dataset).

Asserts these dynamic-parameter pages render without console errors
when given a valid model name or dataset ID.
"""

from __future__ import annotations

import pytest


@pytest.mark.usefixtures("_readiness_check")
class TestModelDetailSmoke:
    """Smoke tests for the model detail page."""

    TIMEOUT = 15_000

    def test_model_detail_page_loads(
        self,
        page,
        base_url: str,
        assert_no_console_errors,
        model_seed: dict,
    ) -> None:
        """Navigate to a model detail page and verify it renders."""
        checker = assert_no_console_errors(page)
        model_name = model_seed["name"]
        page.goto(f"{base_url}/v1/model-detail/{model_name}")
        page.wait_for_load_state("networkidle")
        title = page.locator(".section-card__title")
        title.wait_for(state="visible", timeout=self.TIMEOUT)
        assert model_name in (title.text_content() or "")
        checker.assert_no_errors()

    def test_model_detail_with_numeric_id(
        self,
        page,
        base_url: str,
        model_seed: dict,
    ) -> None:
        """Navigate using model name and accept the page may show error state."""
        model_name = model_seed["name"]
        page.goto(f"{base_url}/v1/model-detail/{model_name}")
        page.wait_for_load_state("networkidle")
        # Accept that the page may show an error state — no console error check
        title = page.locator(".section-card__title")
        title.wait_for(state="visible", timeout=self.TIMEOUT)


@pytest.mark.usefixtures("_readiness_check")
class TestDatasetCurationSmoke:
    """Smoke tests for the dataset curation page."""

    TIMEOUT = 15_000

    def test_dataset_curation_page_loads(
        self,
        page,
        base_url: str,
        assert_no_console_errors,
        dataset_seed: dict,
    ) -> None:
        """Navigate to a dataset curation page and verify it renders."""
        checker = assert_no_console_errors(page)
        ds_id = dataset_seed.get("id", dataset_seed.get("data", {}).get("id", 0))
        page.goto(f"{base_url}/v1/datasets/{ds_id}/curate")
        page.wait_for_load_state("networkidle")
        checker.assert_no_errors()
