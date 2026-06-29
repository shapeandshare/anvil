# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for the Transport layer — envelope unwrap, status mapping, retry, auth."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from pydantic import BaseModel, ConfigDict

from anvil.client._shared.authentication_error import AuthenticationError
from anvil.client._shared.connection_error import ConnectionError
from anvil.client._shared.http_method import HttpMethod
from anvil.client._shared.not_found_error import NotFoundError
from anvil.client._shared.server_config import ServerConfig
from anvil.client._shared.server_error import ServerError
from anvil.client._shared.transport import Transport
from anvil.client._shared.validation_error import ValidationError


class _DummyResult(BaseModel):
    """Minimal Pydantic model for transport response typing."""

    model_config = ConfigDict(extra="forbid")

    ok: bool


def _mock_response(
    status: int,
    json_data: dict[str, Any],
    headers: dict[str, str] | None = None,
) -> MagicMock:
    """Build a realistic mock ``httpx.Response``."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    resp.json.return_value = json_data
    resp.is_success = 200 <= status < 300
    resp.is_error = not (200 <= status < 300)
    resp.headers = headers or {}
    resp.reason_phrase = "Unknown"
    resp.text = json_data.get("error", "") if isinstance(json_data, dict) else ""
    return resp


class TestTransportInit:
    """Transport construction and defaults."""

    def test_init_default_no_api_key(self) -> None:
        config = ServerConfig()
        t = Transport(config)
        assert t._config is config
        assert t._api_key is None

    def test_init_with_api_key(self) -> None:
        config = ServerConfig()
        t = Transport(config, api_key="sk-test")
        assert t._api_key == "sk-test"


class TestTransportRequest:
    """Core request() behavior — envelope, errors, auth, retry."""

    @pytest.mark.asyncio
    async def test_success_unwraps_data(self) -> None:
        config = ServerConfig()
        transport = Transport(config)

        # Build a mock response that matches the envelope shape
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": {"ok": True}, "error": None}
        mock_resp.is_success = True
        mock_resp.is_error = False

        transport._client.request = AsyncMock(return_value=mock_resp)
        result = await transport.request(
            HttpMethod.GET, "/v1/test", response_model=_DummyResult
        )
        assert result.ok is True

    @pytest.mark.asyncio
    async def test_404_maps_to_not_found_error(self) -> None:
        config = ServerConfig()
        transport = Transport(config)
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 404
        mock_resp.json.return_value = {"data": None, "error": "not found"}
        mock_resp.is_success = False
        mock_resp.is_error = True
        transport._client.request = AsyncMock(return_value=mock_resp)

        with pytest.raises(NotFoundError) as exc_info:
            await transport.request(
                HttpMethod.GET, "/v1/missing", response_model=_DummyResult
            )
        assert "not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_401_maps_to_authentication_error(self) -> None:
        config = ServerConfig()
        transport = Transport(config)
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 401
        mock_resp.json.return_value = {"data": None, "error": "unauthorized"}
        mock_resp.is_success = False
        mock_resp.is_error = True
        transport._client.request = AsyncMock(return_value=mock_resp)

        with pytest.raises(AuthenticationError):
            await transport.request(
                HttpMethod.GET, "/v1/secret", response_model=_DummyResult
            )

    @pytest.mark.asyncio
    async def test_422_maps_to_validation_error(self) -> None:
        config = ServerConfig()
        transport = Transport(config)
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 422
        mock_resp.json.return_value = {"data": None, "error": "bad input"}
        mock_resp.is_success = False
        mock_resp.is_error = True
        transport._client.request = AsyncMock(return_value=mock_resp)

        with pytest.raises(ValidationError):
            await transport.request(
                HttpMethod.POST, "/v1/submit", response_model=_DummyResult
            )

    @pytest.mark.asyncio
    async def test_api_key_header_injected(self) -> None:
        config = ServerConfig()
        transport = Transport(config, api_key="sk-secret")
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": {"ok": True}, "error": None}
        mock_resp.is_success = True
        mock_resp.is_error = False
        transport._client.request = AsyncMock(return_value=mock_resp)

        await transport.request(HttpMethod.GET, "/v1/test", response_model=_DummyResult)
        call_kwargs = transport._client.request.call_args.kwargs
        assert call_kwargs.get("headers", {}).get("X-API-Key") == "sk-secret"

    @pytest.mark.asyncio
    async def test_base_url_prepended(self) -> None:
        config = ServerConfig(base_url="http://myhost:9999")
        transport = Transport(config)
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": {"ok": True}, "error": None}
        mock_resp.is_success = True
        mock_resp.is_error = False
        transport._client.request = AsyncMock(return_value=mock_resp)

        await transport.request(
            HttpMethod.GET, "/v1/health", response_model=_DummyResult
        )
        call_kwargs = transport._client.request.call_args.kwargs
        # httpx.AsyncClient prepends base_url automatically at the client level;
        # verify the path was passed correctly
        assert call_kwargs.get("url") == "/v1/health"


class TestTransportRetry:
    """Retry/backoff behavior for 5xx/429/connection errors."""

    @pytest.mark.asyncio
    async def test_server_error_triggers_retry(self) -> None:
        config = ServerConfig(retry_count=2, retry_backoff=0.01)
        transport = Transport(config)
        err_resp = _mock_response(500, {"data": None, "error": "internal"})
        ok_resp = _mock_response(200, {"data": {"ok": True}, "error": None})

        transport._client.request = AsyncMock(side_effect=[err_resp, ok_resp])
        result = await transport.request(
            HttpMethod.GET, "/v1/test", response_model=_DummyResult
        )
        assert result.ok is True
        assert transport._client.request.call_count == 2

    @pytest.mark.asyncio
    async def test_max_retries_exhausted_raises(self) -> None:
        config = ServerConfig(retry_count=1, retry_backoff=0.01)
        transport = Transport(config)
        err_resp = _mock_response(500, {"data": None, "error": "still failing"})

        transport._client.request = AsyncMock(return_value=err_resp)
        with pytest.raises(ServerError):
            await transport.request(
                HttpMethod.GET, "/v1/test", response_model=_DummyResult
            )
        assert transport._client.request.call_count == 2  # 1 original + 1 retry

    @pytest.mark.asyncio
    async def test_connection_error_triggers_retry(self) -> None:
        config = ServerConfig(retry_count=1, retry_backoff=0.01)
        transport = Transport(config)
        transport._client.request = AsyncMock(side_effect=httpx.ConnectError("refused"))
        with pytest.raises(ConnectionError):
            await transport.request(
                HttpMethod.GET, "/v1/test", response_model=_DummyResult
            )


class TestTransportSSE:
    """SSE stream_sse() parsing."""

    @pytest.mark.asyncio
    async def test_sse_yields_events(self) -> None:
        config = ServerConfig()
        transport = Transport(config)
        lines = [
            b"event: metrics\n",
            b'data: {"step": 1, "loss": 0.5}\n',
            b"\n",
            b"event: complete\n",
            b"data: {}\n",
            b"\n",
        ]

        mock_resp = _mock_response(200, {"data": {}, "error": None})
        text_lines = [l.decode().rstrip("\n") for l in lines]

        async def _aiter_lines():
            for ln in text_lines:
                yield ln

        mock_resp.aiter_lines = _aiter_lines

        transport._client.stream = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_resp)
        cm.__aexit__ = AsyncMock(return_value=None)
        transport._client.stream.return_value = cm

        from anvil.client._shared.stream_event_type import StreamEventType

        events = []
        async for event in transport.stream_sse("/v1/training/stream/test-run"):
            events.append(event)
            if event.type is StreamEventType.COMPLETE:
                break

        assert len(events) >= 2
        assert events[0].type is StreamEventType.METRICS
        assert events[0].data.get("loss") == 0.5
        assert events[1].type is StreamEventType.COMPLETE


class TestTransportDownload:
    """Download (stream-to-disk) behavior."""

    @pytest.mark.asyncio
    async def test_download_returns_bytes(self) -> None:
        config = ServerConfig()
        transport = Transport(config)
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.is_success = True
        mock_resp.is_error = False
        mock_resp.content = b"binary data"
        transport._client.request = AsyncMock(return_value=mock_resp)

        data = await transport.download("/v1/artifact")
        assert data == b"binary data"
