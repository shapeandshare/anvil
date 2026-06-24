# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Transport layer — sole holder of httpx primitives.

The ``Transport`` class owns the single ``httpx.AsyncClient`` and performs
all HTTP I/O for the SDK. No layer above Transport touches httpx primitives.
Handles envelope unwrap, status→exception mapping, auth header/cookie
injection, CSRF, retry/backoff, SSE streaming, and file downloads.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict
from pydantic import ValidationError as PydanticValidationError

from anvil.client._shared.server_config import ServerConfig

logger = logging.getLogger(__name__)


class _RawResponse(BaseModel):
    """Minimal Pydantic model for raw envelope validation.

    Accepts extra fields to handle both standard envelope responses
    (``{"data": ..., "error": ...}``) and simple responses
    (e.g. ``{"status": "healthy"}``).
    """

    model_config = ConfigDict(extra="allow")

    data: Any | None = None
    error: str | None = None


class Transport:
    """Owns the single httpx.AsyncClient; performs all HTTP I/O for the SDK.

    Parameters
    ----------
    config : ServerConfig
        Connection configuration (base URL, timeout, retry, backoff).
    api_key : str | None, optional
        API key for ``X-API-Key`` header auth. ``None`` for unauthenticated
        or session-based auth.
    """

    def __init__(
        self,
        config: ServerConfig,
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config: ServerConfig = config
        self._api_key: str | None = api_key
        self._auth_mode: str = "api_key" if api_key else "none"
        self._session_cookies: dict[str, str] = {}

        if client is not None:
            self._client = client
        else:
            self._client = httpx.AsyncClient(
                base_url=config.base_url.rstrip("/"),
                timeout=httpx.Timeout(config.timeout),
            )

    async def request(
        self,
        method: str,
        path: str,
        *,
        response_model: type[BaseModel],
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> BaseModel:
        """Execute a request and return validated ``.data`` of type ``T``.

        Parameters
        ----------
        method : str
            HTTP method (``"GET"``, ``"POST"``, ``"PUT"``, ``"DELETE"``,
            ``"PATCH"``).
        path : str
            URL path (e.g. ``/v1/datasets``).
        response_model : type[BaseModel]
            Pydantic model to deserialize the response ``data`` field into.
        json : dict[str, Any] | None, optional
            JSON request body.
        params : dict[str, Any] | None, optional
            Query string parameters.
        files : dict[str, Any] | None, optional
            Multipart file upload payload.
        idempotency_key : str | None, optional
            Idempotency key for safe retries of non-idempotent methods.

        Returns
        -------
        BaseModel
            The ``.data`` field of the response envelope, parsed into the
            ``response_model`` type.

        Raises
        ------
        ApiError
            Subclass matching the HTTP status or transport error.
        """
        method_str = str(method).upper()
        headers: dict[str, str] = {}
        if self._api_key:
            headers["X-API-Key"] = self._api_key
        if self._auth_mode == "session" and method_str in (
            "POST",
            "PUT",
            "DELETE",
            "PATCH",
        ):

            csrf_token = self._session_cookies.get("_csrf_token")
            if csrf_token:
                headers["X-CSRF-Token"] = csrf_token
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        max_attempts = max(1, self._config.retry_count + 1)

        for attempt in range(max_attempts):
            try:
                response = await self._client.request(
                    method=method_str,
                    url=path,
                    json=json,
                    params=params,
                    files=files,
                    headers=headers if headers else None,
                )
            except httpx.ConnectError as exc:
                if attempt < max_attempts - 1:
                    backoff = self._config.retry_backoff * (2**attempt)
                    logger.debug(
                        "Connection error (attempt %d/%d), retrying in %.2fs: %s",
                        attempt + 1,
                        max_attempts,
                        backoff,
                        exc,
                    )
                    await asyncio.sleep(backoff)
                    continue
                # pylint: disable=redefined-builtin
                from anvil.client._shared.errors.connection_error import (
                    ConnectionError,
                )
                # pylint: enable=redefined-builtin

                raise ConnectionError(str(exc)) from exc

            status = response.status_code

            if status >= 200 and status < 300:
                body = response.json()
                raw = _RawResponse.model_validate(body)
                if raw.error:
                    self._raise_for_status(status, raw.error)
                # Non-envelope response (e.g. {"status": "healthy"}) — use whole body as data
                payload = raw.data if raw.data is not None else body
                # Support both BaseModel subclasses and plain types (dict, list)
                if issubclass(response_model, BaseModel):
                    try:
                        return response_model.model_validate(payload)
                    except PydanticValidationError as exc:
                        raise ValueError(
                            f"Response validation failed for "
                            f"{method_str} {path}: {exc}"
                        ) from exc
                return payload

            if status in (429,) or (status >= 500 and status < 600):
                if attempt < max_attempts - 1 and self._is_retryable(
                    method_str, idempotency_key
                ):
                    retry_after = self._get_retry_after(response)
                    backoff = retry_after or (self._config.retry_backoff * (2**attempt))
                    logger.debug(
                        "HTTP %d (attempt %d/%d), retrying in %.2fs",
                        status,
                        attempt + 1,
                        max_attempts,
                        backoff,
                    )
                    await asyncio.sleep(backoff)
                    continue

            try:
                raw = response.json()
                error_msg = raw.get("error", "") if isinstance(raw, dict) else ""
            except Exception:
                error_msg = response.text
            self._raise_for_status(
                status, error_msg or response.reason_phrase or str(status)
            )

        # Should not reach here, but handle defensively
        raise RuntimeError("Unreachable: all retry attempts exhausted without result")

    async def stream_sse(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> AsyncIterator[BaseModel]:
        """Open an SSE stream and yield typed ``StreamEvent`` objects.

        Parameters
        ----------
        path : str
            The streaming endpoint path (e.g. ``/v1/training/stream/{run_id}``).
        params : dict[str, Any] | None, optional
            Query parameters.

        Yields
        ------
        BaseModel
            Parsed ``StreamEvent`` instances from the event stream.

        Raises
        ------
        ApiError
            On non-2xx response from the stream endpoint.
        """
        from anvil.client._shared.stream_event import StreamEvent
        from anvil.client._shared.stream_event_type import StreamEventType

        headers: dict[str, str] = {}
        if self._api_key:
            headers["X-API-Key"] = self._api_key

        async with self._client.stream(
            "GET", path, params=params, headers=headers or None
        ) as response:
            if response.status_code != 200:
                self._raise_for_status(response.status_code, response.text)
            current_event: str | None = None
            async for line in response.aiter_lines():
                if not line:
                    current_event = None
                    continue
                if line.startswith("event:"):
                    event_name = line[6:].strip()
                    current_event = event_name
                elif line.startswith("data:"):
                    data_str = line[5:].strip()
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        data = {}
                    event_type_str = current_event or "unknown"
                    try:
                        event_type = StreamEventType(event_type_str)
                    except ValueError:
                        event_type = StreamEventType.METRICS  # Graceful fallback
                    yield StreamEvent(type=event_type, data=data)

    async def download(
        self,
        path: str,
        *,
        dest: Path | None = None,
        params: dict[str, Any] | None = None,
    ) -> bytes | Path:
        """Stream a binary response; to ``dest`` if given, else return bytes.

        Parameters
        ----------
        path : str
            Download endpoint path.
        dest : Path | None, optional
            Local path to write the download to. If ``None``, returns bytes.
        params : dict[str, Any] | None, optional
            Query parameters.

        Returns
        -------
        bytes | Path
            ``bytes`` if ``dest`` is ``None``, otherwise ``dest``.
        """
        headers: dict[str, str] = {}
        if self._api_key:
            headers["X-API-Key"] = self._api_key
        response = await self._client.request(
            "GET", path, params=params, headers=headers or None
        )
        response.raise_for_status()

        if dest:
            import aiofiles  # type: ignore[import-untyped]

            content = response.content
            async with aiofiles.open(str(dest), "wb") as f:
                await f.write(content)
            return dest
        return response.content

    async def aclose(self) -> None:
        """Close the underlying httpx AsyncClient."""
        await self._client.aclose()

    def _raise_for_status(self, status: int, message: str) -> None:
        """Map an HTTP status code to a typed ApiError exception and raise it."""
        from anvil.client._shared.errors.api_error import ApiError
        from anvil.client._shared.errors.authentication_error import AuthenticationError
        from anvil.client._shared.errors.not_found_error import NotFoundError
        from anvil.client._shared.errors.rate_limit_error import RateLimitError
        from anvil.client._shared.errors.server_error import ServerError
        from anvil.client._shared.errors.validation_error import ValidationError

        if status in (401, 403):
            raise AuthenticationError(message, status_code=status)
        if status == 404:
            raise NotFoundError(message)
        if status == 422:
            raise ValidationError(message)
        if status == 429:
            retry_after = None
            raise RateLimitError(message, retry_after=retry_after)
        if 500 <= status < 600:
            raise ServerError(message, status_code=status)
        raise ApiError(status_code=status, message=message)

    @staticmethod
    def _is_retryable(method: str, idempotency_key: str | None) -> bool:
        """Determine whether a request can be safely retried."""
        safe_methods = {"GET", "DELETE", "HEAD", "OPTIONS"}
        if method in safe_methods:
            return True
        if idempotency_key is not None:
            return True
        return False

    @staticmethod
    def _get_retry_after(response: httpx.Response) -> float | None:
        """Parse ``Retry-After`` header, return seconds or ``None``."""
        raw = response.headers.get("Retry-After")
        if raw is None:
            return None
        try:
            return float(raw)
        except ValueError:
            return None

    def __repr__(self) -> str:
        return f"Transport(config={self._config!r}, " f"auth_mode={self._auth_mode!r})"
