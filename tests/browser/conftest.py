"""Browser smoke test configuration for anvil.

Provides Playwright page fixtures, compose lifecycle readiness,
console error monitoring, and test data seeding helpers.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import httpx
import pytest

BASE_URL = "http://localhost:8080"
COMPOSE_SERVICE = "anvil"
COMPOSE_FILE = "compose.yaml"
HEALTH_ENDPOINT = f"{BASE_URL}/v1/health"
MLFLOW_API_URL = "http://127.0.0.1:5001/api/2.0/mlflow"
READINESS_RETRIES = 12
READINESS_INTERVAL = 5  # seconds
PAGE_TIMEOUT = 15_000  # milliseconds


# ---------------------------------------------------------------------------
# Readiness wait — session-scoped, runs before any test
# ---------------------------------------------------------------------------


def _wait_for_health(url: str, retries: int, interval: int) -> None:
    """Poll *url* until it returns 200 or *retries* are exhausted."""
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = httpx.get(url, timeout=5)
            if resp.status_code == 200:
                return
        except Exception as exc:
            last_exc = exc
        if attempt < retries:
            time.sleep(interval)
    raise RuntimeError(
        f"Health endpoint {url} not ready after {retries * interval}s"
    ) from last_exc


def _mlflow_experiments_ready(
    mlflow_url: str, retries: int, interval: int
) -> None:
    """Poll the MLflow experiments endpoint until it responds.

    The MLflow sidecar starts independently of the web server. Tests that
    read run history (experiment listing) must wait for this service too.
    """
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = httpx.get(
                f"{mlflow_url}/experiments/list", timeout=5
            )
            if resp.status_code == 200:
                return
        except Exception as exc:
            last_exc = exc
        if attempt < retries:
            time.sleep(interval)
    raise RuntimeError(
        f"MLflow API {mlflow_url} not ready after {retries * interval}s"
    ) from last_exc


@pytest.fixture(scope="session", autouse=True)
def _readiness_check() -> None:
    """Wait for the compose stack (web + MLflow) to be fully available."""
    _wait_for_health(HEALTH_ENDPOINT, READINESS_RETRIES, READINESS_INTERVAL)
    _mlflow_experiments_ready(
        MLFLOW_API_URL, READINESS_RETRIES, READINESS_INTERVAL
    )


# ---------------------------------------------------------------------------
# Page and browser fixtures — rely on pytest-playwright plugin's built-in
# fixtures. Configure via module-level fixture overrides.
# ---------------------------------------------------------------------------


@pytest.fixture
def base_url() -> str:
    """Return the application base URL."""
    return BASE_URL


# pytest-playwright provides ``browser``, ``context``, and ``page``
# automatically. Override the context args fixture to set defaults.


@pytest.fixture(scope="session")
def browser_context_args() -> dict:
    """Default Playwright browser context options."""
    return {
        "ignore_https_errors": True,
        "viewport": {"width": 1280, "height": 720},
    }


@pytest.fixture(autouse=True)
def _configure_page(page):
    page.set_default_timeout(PAGE_TIMEOUT)


# ---------------------------------------------------------------------------
# Console error monitoring helper
# ---------------------------------------------------------------------------


@pytest.fixture
def assert_no_console_errors():
    """Return a helper that attaches error listeners to *page*.

    Usage in a test::

        assert_no_console_errors = request.getfixturevalue(
            "assert_no_console_errors"
        )
        checker = assert_no_console_errors(page)
        # ... interact with page ...
        checker.assert_no_errors()

    The helper collects:
    - ``error``-level console messages (uncaught JS exceptions)
    - ``pageerror`` events (unhandled promise rejections, runtime errors)
    - Failed resource loads (4xx/5xx network responses)

    Warning-level console output is collected for diagnostics only and
    does NOT fail the test (per the Console Error entity in the spec).
    """

    class _ConsoleChecker:
        def __init__(self, page_):
            self._errors: list[str] = []
            self._warnings: list[str] = []
            page_.on("pageerror", self._on_pageerror)
            page_.on("console", self._on_console)
            page_.on("response", self._on_response)

        def _on_pageerror(self, exc):
            self._errors.append(f"PAGE_ERROR: {exc}")

        def _on_console(self, msg):
            if msg.type == "error":
                self._errors.append(f"CONSOLE_ERROR: {msg.text}")
            elif msg.type == "warning":
                self._warnings.append(f"WARNING: {msg.text}")

        def _on_response(self, response):
            status = response.status
            if 400 <= status < 600:
                url = response.url
                self._errors.append(
                    f"FAILED_RESOURCE: {status} {url}"
                )

        def assert_no_errors(self):
            """Assert zero error-level signals were captured.

            Warning-level signals are logged but do not fail.
            """
            assert not self._errors, (
                "Console/network errors detected:\n"
                + "\n".join(self._errors)
            )

        @property
        def warnings(self) -> list[str]:
            return list(self._warnings)

    return _ConsoleChecker


# ---------------------------------------------------------------------------
# Test data seeding fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def seed_client() -> httpx.Client:
    """HTTP client used to seed test data via API (not for assertions)."""
    return httpx.Client(base_url=BASE_URL, timeout=30.0)


@pytest.fixture
def dataset_seed(seed_client: httpx.Client) -> dict:
    """Seed a small dataset via API and return its metadata.

    The dataset is created with a unique name and minimal content so that
    it is available for training tests without exercising the upload UI.
    """
    import uuid

    name = f"test-dataset-{uuid.uuid4().hex[:8]}"
    content = b"hello world this is a tiny test corpus"
    resp = seed_client.post(
        "/v1/datasets/upload",
        files={"file": (f"{name}.txt", content, "text/plain")},
    )
    resp.raise_for_status()
    data = resp.json()
    data["_name"] = name
    return data


@pytest.fixture
def model_seed(seed_client: httpx.Client, dataset_seed: dict) -> dict:
    """Train a tiny toy model via API and register it, returning metadata.

    The model is trained with minimal hyperparameters so it completes in
    seconds and is ready for inference — this is NOT a metadata-only
    registration. If inference-capable seeding via API becomes available,
    this fixture should be updated to use that path instead.
    """
    import uuid

    run_name = f"test-seed-run-{uuid.uuid4().hex[:8]}"

    # Start a training run with minimal config
    train_resp = seed_client.post(
        "/v1/training/start",
        json={
            "dataset_id": dataset_seed["id"],
            "name": run_name,
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

    # Wait for training to complete (poll run status)
    run_id = train_resp.json().get("run_id") or train_resp.json().get("id")
    for _attempt in range(30):
        status_resp = seed_client.get(f"/v1/training/status/{run_id}")
        if status_resp.status_code == 200:
            status_data = status_resp.json()
            if status_data.get("status") in ("completed", "done", "finished"):
                break
        time.sleep(1)
    else:
        raise RuntimeError(
            f"Seed training run {run_id} did not complete in 30s"
        )

    # Export the model so it's available for inference
    export_resp = seed_client.post(
        f"/v1/training/{run_id}/export",
        json={"name": f"test-model-{uuid.uuid4().hex[:8]}"},
    )
    export_resp.raise_for_status()
    return export_resp.json()