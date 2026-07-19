# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""E2E tests for the chat streaming SSE endpoint."""

import httpx
import pytest


@pytest.mark.asyncio
async def test_chat_stream_returns_sse(client: httpx.AsyncClient) -> None:
    """GET /v1/chat/stream returns SSE event-stream format.

    When a model is available the stream produces ``chunk`` events;
    otherwise it returns 404 with a JSON error body.
    """
    r = await client.get(
        "/v1/chat/stream",
        params={"prompt": "Hello", "temperature": 0.7},
    )
    if r.status_code == 200:
        assert "text/event-stream" in r.headers["content-type"]
        assert r.headers.get("cache-control") == "no-cache"
        assert "event: chunk" in r.text or "event: complete" in r.text
    elif r.status_code == 404:
        assert "application/json" in r.headers["content-type"]
        assert "detail" in r.json()
    else:
        pytest.fail(f"Unexpected status code: {r.status_code}")


@pytest.mark.asyncio
async def test_chat_stream_missing_prompt(client: httpx.AsyncClient) -> None:
    """GET /v1/chat/stream without prompt returns 422."""
    r = await client.get("/v1/chat/stream")
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_chat_stream_invalid_temperature(client: httpx.AsyncClient) -> None:
    """GET /v1/chat/stream with temperature out of range returns 422."""
    r = await client.get(
        "/v1/chat/stream",
        params={"prompt": "Hello", "temperature": 3.0},
    )
    assert r.status_code == 422
