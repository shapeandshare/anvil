# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for the Transport layer — envelope unwrap, status mapping,
retry/backoff, auth headers, SSE streaming, and file downloads.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from pydantic import BaseModel, ConfigDict

from anvil.client._shared.api_error import ApiError
from anvil.client._shared.authentication_error import AuthenticationError
from anvil.client._shared.connection_error import ConnectionError
from anvil.client._shared.http_method import HttpMethod
from anvil.client._shared.not_found_error import NotFoundError
from anvil.client._shared.rate_limit_error import RateLimitError
from anvil.client._shared.server_config import ServerConfig
from anvil.client._shared.server_error import ServerError
from anvil.client._shared.stream_event_type import StreamEventType
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
    resp.text = str(json_data) if json_data else ""
    return resp


####################################################################
# Init
####################################################################


class TestTransportInit:
    """Transport construction and defaults."""

    def test_init_default_no_api_key(self) -> None:
        config = ServerConfig()
        t = Transport(config)
        assert t._config is config
        assert t._api_key is None
        assert t._auth_mode == "none"

    def test_init_with_api_key(self) -> None:
        config = ServerConfig()
        t = Transport(config, api_key="sk-test")
        assert t._api_key == "sk-test"
        assert t._auth_mode == "api_key"

    def test_init_with_custom_client(self) -> None:
        config = ServerConfig()
        custom = httpx.AsyncClient()
        t = Transport(config, client=custom)
        assert t._client is custom
        custom.aclose()


####################################################################
# Request — Success / Response Parsing
####################################################################


class TestTransportRequestSuccess:
    """Successful request() calls — envelope unwrap and response parsing."""

    @pytest.mark.asyncio
    async def test_get_request(self) -> None:
        config = ServerConfig()
        transport = Transport(config)
        mock_resp = _mock_response(200, {"data": {"ok": True}, "error": None})
        transport._client.request = AsyncMock(return_value=mock_resp)

        result = await transport.request(
            HttpMethod.GET, "/v1/test", response_model=_DummyResult
        )
        assert result.ok is True
        transport._client.request.assert_called_once()

    @pytest.mark.asyncio
    async def test_post_request(self) -> None:
        config = ServerConfig()
        transport = Transport(config)
        mock_resp = _mock_response(201, {"data": {"ok": True}, "error": None})
        transport._client.request = AsyncMock(return_value=mock_resp)

        result = await transport.request(
            HttpMethod.POST, "/v1/test", json={"key": "val"}, response_model=_DummyResult
        )
        assert result.ok is True
        call_kwargs = transport._client.request.call_args.kwargs
        assert call_kwargs.get("json") == {"key": "val"}

    @pytest.mark.asyncio
    async def test_put_request(self) -> None:
        config = ServerConfig()
        transport = Transport(config)
        mock_resp = _mock_response(200, {"data": {"ok": True}, "error": None})
        transport._client.request = AsyncMock(return_value=mock_resp)

        result = await transport.request(
            HttpMethod.PUT, "/v1/test/1", json={"name": "new"}, response_model=_DummyResult
        )
        assert result.ok is True
        call_kwargs = transport._client.request.call_args.kwargs
        assert call_kwargs.get("url") == "/v1/test/1"
        assert call_kwargs.get("json") == {"name": "new"}

    @pytest.mark.asyncio
    async def test_delete_request(self) -> None:
        config = ServerConfig()
        transport = Transport(config)
        mock_resp = _mock_response(204, {"data": {"ok": True}, "error": None})
        transport._client.request = AsyncMock(return_value=mock_resp)

        result = await transport.request(
            HttpMethod.DELETE, "/v1/test/1", response_model=_DummyResult
        )
        assert result.ok is True

    @pytest.mark.asyncio
    async def test_non_envelope_response_uses_whole_body(self) -> None:
        """Non-envelope response like ``{"status": "healthy"}`` is used as data."""
        config = ServerConfig()
        transport = Transport(config)
        body = {"status": "healthy"}
        mock_resp = _mock_response(200, body)
        mock_resp.json.return_value = body
        transport._client.request = AsyncMock(return_value=mock_resp)

        result = await transport.request(
            HttpMethod.GET, "/v1/health", response_model=dict  # type: ignore[arg-type]
        )
        assert result == {"status": "healthy"}

    @pytest.mark.asyncio
    async def test_params_forwarded(self) -> None:
        config = ServerConfig()
        transport = Transport(config)
        mock_resp = _mock_response(200, {"data": {"ok": True}, "error": None})
        transport._client.request = AsyncMock(return_value=mock_resp)

        await transport.request(
            HttpMethod.GET,
            "/v1/test",
            params={"page": 1, "limit": 10},
            response_model=_DummyResult,
        )
        call_kwargs = transport._client.request.call_args.kwargs
        assert call_kwargs.get("params") == {"page": 1, "limit": 10}


####################################################################
# Request — Header Construction
####################################################################


class TestTransportHeaders:
    """Header injection: API key, CSRF, idempotency key."""

    @pytest.mark.asyncio
    async def test_api_key_header_injected(self) -> None:
        config = ServerConfig()
        transport = Transport(config, api_key="sk-secret")
        mock_resp = _mock_response(200, {"data": {"ok": True}, "error": None})
        transport._client.request = AsyncMock(return_value=mock_resp)

        await transport.request(HttpMethod.GET, "/v1/test", response_model=_DummyResult)
        call_kwargs = transport._client.request.call_args.kwargs
        assert call_kwargs.get("headers", {}).get("X-API-Key") == "sk-secret"

    @pytest.mark.asyncio
    async def test_no_api_key_when_not_provided(self) -> None:
        config = ServerConfig()
        transport = Transport(config)
        mock_resp = _mock_response(200, {"data": {"ok": True}, "error": None})
        transport._client.request = AsyncMock(return_value=mock_resp)

        await transport.request(HttpMethod.GET, "/v1/test", response_model=_DummyResult)
        call_kwargs = transport._client.request.call_args.kwargs
        headers = call_kwargs.get("headers")
        if headers is not None:
            assert "X-API-Key" not in headers

    @pytest.mark.asyncio
    async def test_idempotency_key_header(self) -> None:
        config = ServerConfig()
        transport = Transport(config)
        mock_resp = _mock_response(200, {"data": {"ok": True}, "error": None})
        transport._client.request = AsyncMock(return_value=mock_resp)

        await transport.request(
            HttpMethod.POST,
            "/v1/test",
            response_model=_DummyResult,
            idempotency_key="idem-123",
        )
        call_kwargs = transport._client.request.call_args.kwargs
        assert call_kwargs.get("headers", {}).get("Idempotency-Key") == "idem-123"

    @pytest.mark.asyncio
    async def test_csrf_token_injected_for_session_auth(self) -> None:
        config = ServerConfig()
        transport = Transport(config)
        transport._auth_mode = "session"
        transport._session_cookies["_csrf_token"] = "csrf-secret"
        mock_resp = _mock_response(200, {"data": {"ok": True}, "error": None})
        transport._client.request = AsyncMock(return_value=mock_resp)

        await transport.request(HttpMethod.POST, "/v1/test", response_model=_DummyResult)
        call_kwargs = transport._client.request.call_args.kwargs
        assert call_kwargs.get("headers", {}).get("X-CSRF-Token") == "csrf-secret"

    @pytest.mark.asyncio
    async def test_csrf_token_not_injected_for_get(self) -> None:
        """GET requests don't get CSRF header even in session mode."""
        config = ServerConfig()
        transport = Transport(config)
        transport._auth_mode = "session"
        transport._session_cookies["_csrf_token"] = "csrf-secret"
        mock_resp = _mock_response(200, {"data": {"ok": True}, "error": None})
        transport._client.request = AsyncMock(return_value=mock_resp)

        await transport.request(HttpMethod.GET, "/v1/test", response_model=_DummyResult)
        call_kwargs = transport._client.request.call_args.kwargs
        headers = call_kwargs.get("headers") or {}
        assert "X-CSRF-Token" not in headers

    @pytest.mark.asyncio
    async def test_headers_none_when_empty(self) -> None:
        """When no auth headers are set, headers should be None (not empty dict)."""
        config = ServerConfig()
        transport = Transport(config)
        mock_resp = _mock_response(200, {"data": {"ok": True}, "error": None})
        transport._client.request = AsyncMock(return_value=mock_resp)

        await transport.request(HttpMethod.GET, "/v1/test", response_model=_DummyResult)
        call_kwargs = transport._client.request.call_args.kwargs
        # httpx request accepts headers=None — our transport passes None
        # when there are no custom headers
        assert call_kwargs.get("headers") is None


####################################################################
# Request — Error Handling
####################################################################


class TestTransportErrorHandling:
    """HTTP status → typed exception mapping."""

    @pytest.mark.asyncio
    async def test_401_authentication_error(self) -> None:
        config = ServerConfig(retry_count=0)
        transport = Transport(config)
        mock_resp = _mock_response(401, {"data": None, "error": "unauthorized"})
        transport._client.request = AsyncMock(return_value=mock_resp)

        with pytest.raises(AuthenticationError) as exc:
            await transport.request(HttpMethod.GET, "/v1/secret", response_model=_DummyResult)
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_403_authentication_error(self) -> None:
        config = ServerConfig(retry_count=0)
        transport = Transport(config)
        mock_resp = _mock_response(403, {"data": None, "error": "forbidden"})
        transport._client.request = AsyncMock(return_value=mock_resp)

        with pytest.raises(AuthenticationError) as exc:
            await transport.request(HttpMethod.GET, "/v1/secret", response_model=_DummyResult)
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_404_not_found_error(self) -> None:
        config = ServerConfig(retry_count=0)
        transport = Transport(config)
        mock_resp = _mock_response(404, {"data": None, "error": "not found"})
        transport._client.request = AsyncMock(return_value=mock_resp)

        with pytest.raises(NotFoundError) as exc:
            await transport.request(HttpMethod.GET, "/v1/missing", response_model=_DummyResult)
        assert "not found" in str(exc.value)

    @pytest.mark.asyncio
    async def test_422_validation_error(self) -> None:
        config = ServerConfig(retry_count=0)
        transport = Transport(config)
        mock_resp = _mock_response(422, {"data": None, "error": "bad input"})
        transport._client.request = AsyncMock(return_value=mock_resp)

        with pytest.raises(ValidationError) as exc:
            await transport.request(
                HttpMethod.POST, "/v1/submit", response_model=_DummyResult
            )
        assert exc.value.status_code == 422

    @pytest.mark.asyncio
    async def test_429_rate_limit_error(self) -> None:
        config = ServerConfig(retry_count=0)
        transport = Transport(config)
        mock_resp = _mock_response(429, {"data": None, "error": "too many requests"})
        transport._client.request = AsyncMock(return_value=mock_resp)

        with pytest.raises(RateLimitError) as exc:
            await transport.request(HttpMethod.GET, "/v1/rate", response_model=_DummyResult)
        assert exc.value.status_code == 429

    @pytest.mark.asyncio
    async def test_500_server_error(self) -> None:
        config = ServerConfig(retry_count=0)
        transport = Transport(config)
        mock_resp = _mock_response(500, {"data": None, "error": "internal error"})
        transport._client.request = AsyncMock(return_value=mock_resp)

        with pytest.raises(ServerError) as exc:
            await transport.request(
                HttpMethod.GET, "/v1/error", response_model=_DummyResult
            )
        assert exc.value.status_code == 500

    @pytest.mark.asyncio
    async def test_503_server_error(self) -> None:
        config = ServerConfig(retry_count=0)
        transport = Transport(config)
        mock_resp = _mock_response(503, {"data": None, "error": "service unavailable"})
        transport._client.request = AsyncMock(return_value=mock_resp)

        with pytest.raises(ServerError) as exc:
            await transport.request(
                HttpMethod.GET, "/v1/unavailable", response_model=_DummyResult
            )
        assert exc.value.status_code == 503

    @pytest.mark.asyncio
    async def test_generic_400_api_error(self) -> None:
        config = ServerConfig(retry_count=0)
        transport = Transport(config)
        mock_resp = _mock_response(400, {"data": None, "error": "bad request"})
        transport._client.request = AsyncMock(return_value=mock_resp)

        with pytest.raises(ApiError) as exc:
            await transport.request(
                HttpMethod.GET, "/v1/bad", response_model=_DummyResult
            )
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_connection_error_raises_typed_exception(self) -> None:
        config = ServerConfig(retry_count=0)
        transport = Transport(config)
        transport._client.request = AsyncMock(side_effect=httpx.ConnectError("refused"))

        with pytest.raises(ConnectionError) as exc:
            await transport.request(HttpMethod.GET, "/v1/test", response_model=_DummyResult)
        assert "refused" in str(exc.value)

    @pytest.mark.asyncio
    async def test_200_with_error_body_raises(self) -> None:
        """Even a 200 response can carry an error in the envelope."""
        config = ServerConfig(retry_count=0)
        transport = Transport(config)
        mock_resp = _mock_response(
            200, {"data": None, "error": "server-side processing error"}
        )
        transport._client.request = AsyncMock(return_value=mock_resp)

        with pytest.raises(ApiError) as exc:
            await transport.request(
                HttpMethod.GET, "/v1/test", response_model=_DummyResult
            )
        assert "server-side processing error" in str(exc.value)

    @pytest.mark.asyncio
    async def test_response_validation_failure_raises_value_error(self) -> None:
        """When response data doesn't match the model, raises ValueError."""
        config = ServerConfig()
        transport = Transport(config)
        # _DummyResult requires 'ok' field — missing it
        mock_resp = _mock_response(200, {"data": {"nope": True}, "error": None})
        transport._client.request = AsyncMock(return_value=mock_resp)

        with pytest.raises(ValueError, match="Response validation failed"):
            await transport.request(
                HttpMethod.GET, "/v1/test", response_model=_DummyResult
            )


####################################################################
# Retry / Backoff / Rate Limiting
####################################################################


class TestTransportRetry:
    """Retry/backoff behavior for 5xx, 429, and connection errors."""

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
        # 1 original + 1 retry (retry_count=1)
        assert transport._client.request.call_count == 2

    @pytest.mark.asyncio
    async def test_rate_limit_triggers_retry(self) -> None:
        config = ServerConfig(retry_count=2, retry_backoff=0.01)
        transport = Transport(config)
        err_resp = _mock_response(429, {"data": None, "error": "rate limited"})
        ok_resp = _mock_response(200, {"data": {"ok": True}, "error": None})

        transport._client.request = AsyncMock(side_effect=[err_resp, ok_resp])
        result = await transport.request(
            HttpMethod.GET, "/v1/test", response_model=_DummyResult
        )
        assert result.ok is True
        assert transport._client.request.call_count == 2

    @pytest.mark.asyncio
    async def test_connection_error_triggers_retry(self) -> None:
        config = ServerConfig(retry_count=1, retry_backoff=0.01)
        transport = Transport(config)
        transport._client.request = AsyncMock(side_effect=httpx.ConnectError("refused"))
        with pytest.raises(ConnectionError):
            await transport.request(
                HttpMethod.GET, "/v1/test", response_model=_DummyResult
            )

    @pytest.mark.asyncio
    async def test_connection_error_succeeds_on_retry(self) -> None:
        config = ServerConfig(retry_count=2, retry_backoff=0.01)
        transport = Transport(config)
        ok_resp = _mock_response(200, {"data": {"ok": True}, "error": None})
        transport._client.request = AsyncMock(
            side_effect=[httpx.ConnectError("timeout"), ok_resp]
        )
        result = await transport.request(
            HttpMethod.GET, "/v1/test", response_model=_DummyResult
        )
        assert result.ok is True
        assert transport._client.request.call_count == 2

    @pytest.mark.asyncio
    async def test_non_retryable_method_not_retried_on_5xx(self) -> None:
        """POST without idempotency key should NOT retry on 5xx."""
        config = ServerConfig(retry_count=2, retry_backoff=0.01)
        transport = Transport(config)
        err_resp = _mock_response(500, {"data": None, "error": "internal"})

        transport._client.request = AsyncMock(return_value=err_resp)
        with pytest.raises(ServerError):
            await transport.request(
                HttpMethod.POST, "/v1/test", response_model=_DummyResult
            )
        # Only 1 attempt — POST without idempotency key is not retryable
        # Actually wait — looking at the code: for 5xx/429, it checks
        # _is_retryable(method_str, idempotency_key). POST without
        # idempotency key should NOT be retryable.
        # But — retry_count=2 means max_attempts=3, and the code attempts
        # all attempts even for non-retryable... no, look at the code:
        #
        # if status in (429,) or (status >= 500 and status < 600):
        #     if attempt < max_attempts - 1 and self._is_retryable(...):
        #         retry...
        #         continue
        # # Falls through to _raise_for_status
        #
        # So non-retryable 5xx falls through and raises immediately.
        # Call count should be 1.
        assert transport._client.request.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_after_header_used_when_present(self) -> None:
        """The Retry-After header is parsed and used for backoff."""
        config = ServerConfig(retry_count=1, retry_backoff=10.0)
        transport = Transport(config)
        err_resp = _mock_response(
            429, {"data": None, "error": "rate limited"}, headers={"Retry-After": "0.01"}
        )
        ok_resp = _mock_response(200, {"data": {"ok": True}, "error": None})

        transport._client.request = AsyncMock(side_effect=[err_resp, ok_resp])
        result = await transport.request(
            HttpMethod.GET, "/v1/test", response_model=_DummyResult
        )
        assert result.ok is True
        # Used Retry-After (0.01) instead of backoff (10.0) — so it succeeded quickly
        assert transport._client.request.call_count == 2

    @pytest.mark.asyncio
    async def test_no_retry_when_retry_count_zero(self) -> None:
        config = ServerConfig(retry_count=0, retry_backoff=0.01)
        transport = Transport(config)
        err_resp = _mock_response(500, {"data": None, "error": "fail"})
        transport._client.request = AsyncMock(return_value=err_resp)

        with pytest.raises(ServerError):
            await transport.request(
                HttpMethod.GET, "/v1/test", response_model=_DummyResult
            )
        assert transport._client.request.call_count == 1


####################################################################
# SSE Streaming
####################################################################


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

        events = []
        async for event in transport.stream_sse("/v1/training/stream/test-run"):
            events.append(event)
            if event.type is StreamEventType.COMPLETE:
                break

        assert len(events) >= 2
        assert events[0].type is StreamEventType.METRICS
        assert events[0].data.get("loss") == 0.5
        assert events[1].type is StreamEventType.COMPLETE

    @pytest.mark.asyncio
    async def test_sse_injects_api_key_header(self) -> None:
        config = ServerConfig()
        transport = Transport(config, api_key="sk-stream")
        mock_resp = _mock_response(200, {"data": {}, "error": None})

        async def _empty_lines():
            """Empty async generator for aiter_lines mock."""
            if False:
                yield ""  # pragma: no cover

        mock_resp.aiter_lines = _empty_lines  # type: ignore[assignment]

        transport._client.stream = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_resp)
        cm.__aexit__ = AsyncMock(return_value=None)
        transport._client.stream.return_value = cm

        async for _ in transport.stream_sse("/v1/stream"):
            break

        call_kwargs = transport._client.stream.call_args.kwargs
        assert call_kwargs.get("headers", {}).get("X-API-Key") == "sk-stream"

    @pytest.mark.asyncio
    async def test_sse_non_200_raises(self) -> None:
        config = ServerConfig()
        transport = Transport(config)
        mock_resp = _mock_response(404, {"data": None, "error": "not found"})

        async def _empty_lines():
            """Empty async generator for aiter_lines mock."""
            if False:
                yield ""  # pragma: no cover

        mock_resp.aiter_lines = _empty_lines  # type: ignore[assignment]

        transport._client.stream = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_resp)
        cm.__aexit__ = AsyncMock(return_value=None)
        transport._client.stream.return_value = cm

        with pytest.raises(NotFoundError):
            async for _ in transport.stream_sse("/v1/stream"):
                pass


####################################################################
# Download
####################################################################


class TestTransportDownload:
    """Download (stream-to-disk and in-memory) behavior."""

    @pytest.mark.asyncio
    async def test_download_returns_bytes(self) -> None:
        config = ServerConfig()
        transport = Transport(config)
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.content = b"binary data"
        transport._client.request = AsyncMock(return_value=mock_resp)

        data = await transport.download("/v1/artifact")
        assert data == b"binary data"

    @pytest.mark.asyncio
    async def test_download_to_disk(self, tmp_path: Path) -> None:
        config = ServerConfig()
        transport = Transport(config)
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.content = b"file content"
        transport._client.request = AsyncMock(return_value=mock_resp)

        dest = tmp_path / "model.safetensors"
        with patch("anvil.client._shared.transport.aiofiles") as mock_aiofiles:
            mock_file = AsyncMock()
            mock_aiofiles.open.return_value.__aenter__ = AsyncMock(return_value=mock_file)
            mock_aiofiles.open.return_value.__aexit__ = AsyncMock()
            result = await transport.download("/v1/artifact", dest=dest)
            assert result == dest
            mock_file.write.assert_called_once_with(b"file content")

    @pytest.mark.asyncio
    async def test_download_to_disk_raises_without_aiofiles(self) -> None:
        """Without aiofiles, download to disk raises ImportError."""
        config = ServerConfig()
        transport = Transport(config)
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.content = b"file content"
        transport._client.request = AsyncMock(return_value=mock_resp)

        dest = Path("/tmp/out.bin")
        with patch("anvil.client._shared.transport.aiofiles", None):
            with pytest.raises(ImportError, match="aiofiles is required"):
                await transport.download("/v1/artifact", dest=dest)

    @pytest.mark.asyncio
    async def test_download_injects_api_key(self) -> None:
        config = ServerConfig()
        transport = Transport(config, api_key="sk-dl")
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.content = b"data"
        transport._client.request = AsyncMock(return_value=mock_resp)

        await transport.download("/v1/artifact")
        call_kwargs = transport._client.request.call_args.kwargs
        assert call_kwargs.get("headers", {}).get("X-API-Key") == "sk-dl"


####################################################################
# Lifecycle and repr
####################################################################


class TestTransportLifecycle:
    """aclose, repr, and misc utilities."""

    @pytest.mark.asyncio
    async def test_aclose(self) -> None:
        config = ServerConfig()
        transport = Transport(config)
        transport._client.aclose = AsyncMock()
        await transport.aclose()
        transport._client.aclose.assert_called_once()

    def test_repr(self) -> None:
        config = ServerConfig()
        t = Transport(config, api_key="sk-test")
        r = repr(t)
        assert "Transport" in r
        assert "auth_mode='api_key'" in r

    def test_repr_no_auth(self) -> None:
        config = ServerConfig()
        t = Transport(config)
        r = repr(t)
        assert "auth_mode='none'" in r

    def test_is_retryable_safe_methods(self) -> None:
        assert Transport._is_retryable("GET", None) is True
        assert Transport._is_retryable("DELETE", None) is True
        assert Transport._is_retryable("HEAD", None) is True
        assert Transport._is_retryable("OPTIONS", None) is True

    def test_is_retryable_post_without_idempotency_key(self) -> None:
        assert Transport._is_retryable("POST", None) is False

    def test_is_retryable_post_with_idempotency_key(self) -> None:
        assert Transport._is_retryable("POST", "idem-1") is True

    def test_get_retry_after_parsed(self) -> None:
        resp = MagicMock(spec=httpx.Response)
        resp.headers = {"Retry-After": "2.5"}
        assert Transport._get_retry_after(resp) == 2.5

    def test_get_retry_after_missing(self) -> None:
        resp = MagicMock(spec=httpx.Response)
        resp.headers = {}
        assert Transport._get_retry_after(resp) is None

    def test_get_retry_after_invalid(self) -> None:
        resp = MagicMock(spec=httpx.Response)
        resp.headers = {"Retry-After": "not-a-number"}
        assert Transport._get_retry_after(resp) is None
