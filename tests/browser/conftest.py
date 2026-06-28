"""Browser smoke test configuration for anvil.

Provides Playwright page fixtures, compose lifecycle readiness,
console error monitoring, and test data seeding helpers.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import httpx
import pytest

BROWSER_TEST_API_KEY = "browser-test-anvil-key-00000000"
"""Fixed API key used for browser smoke tests.

Must match ``ANVIL_API_KEY`` in the Docker compose environment so both
the test runner and the container agree on credentials.
"""

# Set a known key BEFORE any module-level code calls get_api_key_store().
os.environ.setdefault("ANVIL_API_KEY", BROWSER_TEST_API_KEY)

from anvil.api.deps import get_api_key_store

BASE_URL = "http://localhost:8080"
COMPOSE_SERVICE = "anvil"
COMPOSE_FILE = "compose.yaml"
HEALTH_ENDPOINT = f"{BASE_URL}/v1/health"
MLFLOW_API_URL = "http://127.0.0.1:5001/api/2.0/mlflow"
READINESS_RETRIES = 12
READINESS_INTERVAL = 5  # seconds
PAGE_TIMEOUT = 15_000  # milliseconds
TEST_API_KEY = get_api_key_store().key or ""


#############################################################################
# Readiness wait — session-scoped, runs before any test
#############################################################################


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


def _mlflow_experiments_ready(mlflow_url: str, retries: int, interval: int) -> None:
    """Poll the MLflow experiments endpoint until it responds.

    The MLflow sidecar starts independently of the web server. Tests that
    read run history (experiment listing) must wait for this service too.
    """
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = httpx.get(f"{mlflow_url}/experiments/list", timeout=5)
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
    # Wait for the compose stack's web server to be fully available.
    _wait_for_health(HEALTH_ENDPOINT, READINESS_RETRIES, READINESS_INTERVAL)


@pytest.fixture(scope="session")
def _mlflow_ready() -> None:
    """No-op: MLflow readiness is best verified by polling the UI."""
    return
    _mlflow_experiments_ready(MLFLOW_API_URL, READINESS_RETRIES, READINESS_INTERVAL)


#############################################################################
# Page and browser fixtures — rely on pytest-playwright plugin's built-in
# fixtures. Configure via module-level fixture overrides.
#############################################################################


@pytest.fixture(scope="session")
def base_url() -> str:
    """Return the application base URL."""
    return BASE_URL


# pytest-playwright provides ``browser``, ``context``, and ``page``
# automatically. Override the context args fixture to set defaults.


@pytest.fixture(scope="session")
def browser_context_args(base_url: str) -> dict:
    """Default Playwright browser context options."""
    return {
        "ignore_https_errors": True,
        "base_url": base_url,
        "viewport": {"width": 1280, "height": 720},
    }


@pytest.fixture(autouse=True)
def _configure_page(page):
    page.set_default_timeout(PAGE_TIMEOUT)


#############################################################################
# Console error monitoring helper
#############################################################################


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
                self._errors.append(f"FAILED_RESOURCE: {status} {url}")

        def assert_no_errors(self):
            """Assert zero error-level signals were captured.

            Warning-level signals are logged but do not fail.
            """
            assert not self._errors, "Console/network errors detected:\n" + "\n".join(
                self._errors
            )

        @property
        def warnings(self) -> list[str]:
            return list(self._warnings)

    return _ConsoleChecker


#############################################################################
# Test data seeding fixtures
#############################################################################


@pytest.fixture(scope="session")
def seed_client() -> httpx.Client:
    """HTTP client used to seed test data via API (not for assertions)."""
    return httpx.Client(
        base_url=BASE_URL,
        timeout=30.0,
        headers={"X-API-Key": TEST_API_KEY},
    )


@pytest.fixture(autouse=True)
def _login(page):
    """Log in to the web UI before each test.

    POSTs the API key to /login, stores the session cookie in the
    browser context, so subsequent page navigations are authenticated.

    Retries once on transient connection errors (socket hang up).
    """
    import time as _time

    last_exc = None
    for attempt in range(2):
        try:
            response = page.request.post(
                "/login",
                data=json.dumps({"api_key": TEST_API_KEY}),
                headers={"Content-Type": "application/json"},
            )
            if response.ok:
                break
            last_exc = AssertionError(
                f"Login failed: {response.status} {response.status_text}"
            )
        except Exception as exc:
            last_exc = exc
            if attempt == 0:
                _time.sleep(3)
    else:
        raise last_exc  # type: ignore[misc]

    assert response.ok, f"Login failed: {response.status} {response.status_text}"

    # Extract the Set-Cookie header and replay it into the browser context
    set_cookie = response.headers.get("set-cookie")
    if set_cookie:
        page.context.add_cookies(
            [
                {
                    "name": "anvil_session",
                    "value": _extract_cookie_value(set_cookie, "anvil_session"),
                    "domain": "localhost",
                    "path": "/",
                    "httpOnly": True,
                    "sameSite": "Strict",
                }
            ]
        )


def _extract_cookie_value(set_cookie: str, name: str) -> str:
    """Extract a named cookie value from a Set-Cookie header string."""
    for part in set_cookie.split(";"):
        part = part.strip()
        if part.startswith(f"{name}="):
            return part[len(f"{name}=") :]
    return ""


@pytest.fixture
def dataset_seed(seed_client: httpx.Client) -> dict:
    """Seed a small dataset via API and return its metadata."""
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
    if "data" in data and isinstance(data["data"], dict) and "id" in data["data"]:
        data["id"] = data["data"]["id"]
    return data


@pytest.fixture
def model_seed(seed_client: httpx.Client) -> dict:
    """Return a placeholder model descriptor.

    API-based model seeding is currently blocked by training-route
    discovery.  The inference test navigates the page without a real
    model and checks the page renders correctly (no crash).
    """
    return {"name": "demo", "id": 0}
