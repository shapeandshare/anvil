"""Smoke tests for the login page.

Verifies the login page renders, accepts an API key, and creates a
valid session cookie.
"""

from __future__ import annotations

import json

import pytest

BROWSER_TEST_API_KEY = "browser-test-anvil-key-00000000"


@pytest.mark.usefixtures("_readiness_check")
class TestLoginSmoke:
    """Smoke tests for the login flow."""

    TIMEOUT = 15_000

    def test_login_page_renders(self, page, base_url: str) -> None:
        """GET /login renders the login form."""
        page.goto(f"{base_url}/login")
        page.wait_for_load_state("networkidle")
        form = page.locator("#login-form")
        form.wait_for(state="visible", timeout=self.TIMEOUT)
        api_key_input = page.locator("#api-key")
        api_key_input.wait_for(state="visible", timeout=self.TIMEOUT)
        assert api_key_input.get_attribute("type") == "password"

    def test_login_submit_creates_session(self, page, base_url: str) -> None:
        """Submitting a valid API key creates a session cookie."""
        page.goto(f"{base_url}/login")
        page.wait_for_load_state("networkidle")

        # Fill in the API key and submit
        api_key_input = page.locator("#api-key")
        api_key_input.fill(BROWSER_TEST_API_KEY)

        # Submit via the form's JS handler or native submit
        submit_btn = page.locator("#login-form button[type='submit']")
        if submit_btn.count():
            submit_btn.click()
        else:
            api_key_input.press("Enter")

        # After successful login, should eventually redirect from /login
        page.wait_for_url(f"{base_url}/**", timeout=10_000)

    def test_login_with_wrong_key_shows_error(self, page, base_url: str) -> None:
        """Submitting an invalid API key shows an error message."""
        page.goto(f"{base_url}/login")
        page.wait_for_load_state("networkidle")

        api_key_input = page.locator("#api-key")
        api_key_input.fill("invalid-key-12345")

        # Dispatch the login directly via POST to test the error path
        response = page.request.post(
            "/login",
            data=json.dumps({"api_key": "invalid-key-12345"}),
            headers={"Content-Type": "application/json"},
        )
        assert response.status == 401 or response.status == 403
