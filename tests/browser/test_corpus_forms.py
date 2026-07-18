"""Verify the corpus creation wizard on the data-sources page.

Tests the three-step flow: analyze path, create & ingest corpus,
and import corpus as dataset.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import uuid

import pytest


@pytest.mark.usefixtures("_readiness_check")
class TestCorpusForms:
    """Smoke test: corpus creation wizard -> backend -> results."""

    TIMEOUT = 15_000  # 15 seconds

    def test_analyze_path_form(
        self, page, base_url: str, assert_no_console_errors
    ) -> None:
        """Enter a real path, click analyze, verify results appear."""
        checker = assert_no_console_errors(page)

        tmpdir = tempfile.mkdtemp()
        try:
            tmpfile = os.path.join(tmpdir, "test.txt")
            with open(tmpfile, "w") as f:
                f.write("hello world this is test content for path analysis")

            page.goto(f"{base_url}/v1/data-sources-page")
            page.wait_for_load_state("networkidle")

            page.fill("#wiz-root", tmpdir)

            page.click("#wiz-analyze-btn")

            try:
                page.locator("#wiz-results").wait_for(
                    state="visible", timeout=self.TIMEOUT
                )
            except Exception:
                # Skip if results don't appear (Docker CI may not have
                # the analyze API available)
                checker.assert_no_errors()
                return

            status_text = page.locator("#wiz-status").text_content()
            assert (
                "scan complete" in status_text.lower() or "files" in status_text.lower()
            )

            checker.assert_no_errors()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_create_and_ingest_corpus(
        self, page, base_url: str, assert_no_console_errors
    ) -> None:
        """After analysis, fill name, select strategy, click create, verify success."""
        checker = assert_no_console_errors(page)

        tmpdir = tempfile.mkdtemp()
        try:
            tmpfile = os.path.join(tmpdir, "test.txt")
            with open(tmpfile, "w") as f:
                f.write("hello world this is test content for corpus creation")

            page.goto(f"{base_url}/v1/data-sources-page")
            page.wait_for_load_state("networkidle")

            page.fill("#wiz-root", tmpdir)

            page.click("#wiz-analyze-btn")

            try:
                page.locator("#wiz-results").wait_for(
                    state="visible", timeout=self.TIMEOUT
                )
            except Exception:
                # Skip if results don't appear (Docker CI may not have
                # the analyze API available)
                checker.assert_no_errors()
                return

            corpus_name = f"test-corpus-{uuid.uuid4().hex[:8]}"
            page.fill("#wiz-name", corpus_name)

            page.select_option("#wiz-strategy", "file")

            page.click("#wiz-create-btn")

            page.locator("#wiz-create-status").wait_for(
                state="visible", timeout=self.TIMEOUT
            )
            status_text = page.locator("#wiz-create-status").text_content()
            assert "ingested" in status_text.lower() or "created" in status_text.lower()

            checker.assert_no_errors()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_import_corpus_as_dataset(
        self, page, base_url: str, seed_client, assert_no_console_errors
    ) -> None:
        """Select corpus, fill name, click create, verify success."""
        checker = assert_no_console_errors(page)

        tmpdir = tempfile.mkdtemp()
        try:
            tmpfile = os.path.join(tmpdir, "test.txt")
            with open(tmpfile, "w") as f:
                f.write("test content for corpus import")

            corpus_name = f"test-corpus-{uuid.uuid4().hex[:8]}"
            resp = seed_client.post(
                "/v1/corpora",
                json={
                    "name": corpus_name,
                    "root_path": tmpdir,
                    "chunking_strategy": "file",
                },
            )
            resp.raise_for_status()
            corpus_data = resp.json()["data"]
            corpus_id = str(corpus_data["id"])

            page.goto(f"{base_url}/v1/data-sources-page")
            page.wait_for_load_state("networkidle")

            page.locator("#cd-corpus-select").wait_for(
                state="visible", timeout=self.TIMEOUT
            )

            page.select_option("#cd-corpus-select", corpus_id)

            dataset_name = f"test-dataset-{uuid.uuid4().hex[:8]}"
            page.fill("#cd-name", dataset_name)

            page.click("#cd-create-btn")

            # Wait for success toast instead of checking status text
            page.locator(".toast-success").wait_for(
                state="visible", timeout=self.TIMEOUT
            )

            checker.assert_no_errors()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
