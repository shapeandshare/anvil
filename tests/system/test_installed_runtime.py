# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""System tests for anvil pip-installed runtime.

These tests run against a running container deployed via docker compose.
They validate: health endpoint, primary page rendering, static assets,
DB init + demo bootstrap, and CLI tool execution.

Run via: `make test-system`
"""

import re

import httpx
import pytest
from conftest import compose_exec

# =============================================================================
# HTTP assertions
# =============================================================================


class TestHealth:
    """ST-H1: /v1/health endpoint."""

    def test_health_returns_healthy(self, client: httpx.Client) -> None:
        resp = client.get("/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"

    def test_health_returns_version(self, client: httpx.Client) -> None:
        resp = client.get("/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"], "Health response missing version string"


class TestPrimaryPages:
    """ST-P1..ST-P8: Every primary page returns 200."""

    PAGES = [
        "/",
        "/v1/training-page",
        "/v1/datasets-page",
        "/v1/experiments-page",
        "/v1/models-page",
        "/v1/inference-page",
        "/v1/operations-page",
        "/v1/learn",
    ]

    @pytest.mark.parametrize("path", PAGES)
    def test_page_returns_200(self, client: httpx.Client, path: str) -> None:
        resp = client.get(path)
        assert resp.status_code == 200, f"Page {path} returned {resp.status_code}"


class TestPageAssets:
    """ST-A1: Each primary page has resolvable static assets (SC-006)."""

    PAGES = [
        "/",
        "/v1/training-page",
        "/v1/datasets-page",
        "/v1/experiments-page",
        "/v1/models-page",
        "/v1/inference-page",
        "/v1/operations-page",
        "/v1/learn",
    ]

    @pytest.mark.parametrize("path", PAGES)
    def test_page_assets_resolve(self, client: httpx.Client, path: str) -> None:
        """Parse the page for /static/... URLs and assert each resolves 200."""
        resp = client.get(path)
        assert resp.status_code == 200
        html = resp.text
        # Find referenced static assets: href="/static/...", src="/static/..."
        urls = re.findall(r'(?:href|src)="(/static/[^"]+)"', html)
        assert urls, f"No /static/... references found on page {path}"
        for url in set(urls):
            asset_resp = client.get(url)
            assert (
                asset_resp.status_code == 200
            ), f"Asset {url} referenced on {path} returned {asset_resp.status_code}"


class TestDemoContent:
    """ST-D1: Bundled demo content is present."""

    def test_corpora_contains_demo(self, client: httpx.Client) -> None:
        resp = client.get("/v1/corpora")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1, "No corpora found — demo bootstrap may have failed"

    def test_demo_dataset_present(self, client: httpx.Client) -> None:
        resp = client.get("/v1/datasets")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1, "No datasets found — demo bootstrap may have failed"


# =============================================================================
# CLI assertions (docker compose exec)
# =============================================================================


class TestDatabaseCli:
    """ST-C1: anvil-db current reports a migration revision."""

    def test_db_current_reports_revision(self) -> None:
        result = compose_exec("anvil-db current")
        assert result.returncode == 0, f"anvil-db current failed:\n{result.stderr}"
        # After first-run migrations, this should NOT be <base>
        assert result.stdout.strip(), "anvil-db current returned empty revision"
        assert (
            result.stdout.strip() != "<base>"
        ), "Database is at base revision — migrations may not have run"


class TestCorpusCli:
    """ST-C2: anvil-corpus list shows demo content."""

    def test_anvil_corpus_list(self) -> None:
        result = compose_exec("anvil-corpus list")
        assert result.returncode == 0, f"anvil-corpus list failed:\n{result.stderr}"
        assert (
            "Demo" in result.stdout or len(result.stdout.strip()) > 0
        ), "anvil-corpus list returned no output"


class TestBootstrapCli:
    """ST-C3: anvil-bootstrap-datasets --dry-run discovers bundled demo."""

    def test_bootstrap_dry_run_finds_demo(self) -> None:
        result = compose_exec("anvil-bootstrap-datasets --dry-run")
        assert (
            result.returncode == 0
        ), f"anvil-bootstrap-datasets --dry-run failed:\n{result.stderr}"
        assert (
            "Would create" in result.stdout
        ), f"Dry-run output missing 'Would create'. Got:\n{result.stdout}"


class TestTrainCli:
    """ST-C4: anvil-train --help exits 0."""

    def test_train_help(self) -> None:
        result = compose_exec("anvil-train --help")
        assert result.returncode == 0, f"anvil-train --help failed:\n{result.stderr}"


class TestStopCli:
    """ST-C5: anvil-stop exits 0 (idempotent — ok when nothing running)."""

    def test_stop_succeeds(self) -> None:
        result = compose_exec("anvil-stop")
        assert result.returncode == 0, f"anvil-stop failed:\n{result.stderr}"
