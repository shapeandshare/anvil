# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""E2E tests for the HuggingFace Model Browser page and search API.

Tests the ``/v1/hf-browser`` page-rendering route and the
``/v1/hf-browser/search`` JSON search endpoint.  The search endpoint
returns ``200`` when the ``[finetune]`` extra is installed and ``503``
when it is not.
"""

from __future__ import annotations

import httpx
import pytest


@pytest.mark.asyncio
async def test_hf_browser_page_returns_200(client: httpx.AsyncClient) -> None:
    """GET /v1/hf-browser returns the HuggingFace Model Browser page.

    Asserts the response status is ``200`` and the content type
    indicates HTML.
    """
    r = await client.get("/v1/hf-browser")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


@pytest.mark.asyncio
async def test_hf_browser_search_returns_json(client: httpx.AsyncClient) -> None:
    """GET /v1/hf-browser/search?q=TinyLlama returns JSON or 503.

    When the ``[finetune]`` extra is installed the search endpoint
    queries HuggingFace Hub and returns ``200`` with a JSON payload.
    Without the extra it returns ``503`` with an error body.
    """
    r = await client.get("/v1/hf-browser/search?q=TinyLlama")
    assert r.status_code in (
        200,
        503,
    ), f"Expected 200 or 503, got {r.status_code}: {r.text}"
    if r.status_code == 200:
        data = r.json()
        assert "results" in data
    elif r.status_code == 503:
        data = r.json()
        assert "error" in data
        assert "code" in data
