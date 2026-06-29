# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for the SDK error hierarchy — status→exception mapping."""

from __future__ import annotations

import pytest

from anvil.client._shared.api_error import ApiError
from anvil.client._shared.authentication_error import AuthenticationError
from anvil.client._shared.connection_error import ConnectionError
from anvil.client._shared.not_found_error import NotFoundError
from anvil.client._shared.rate_limit_error import RateLimitError
from anvil.client._shared.server_error import ServerError
from anvil.client._shared.validation_error import ValidationError


class TestErrorHierarchy:
    """Structural tests for the typed exception hierarchy."""

    def test_all_errors_subclass_api_error(self) -> None:
        assert issubclass(AuthenticationError, ApiError)
        assert issubclass(NotFoundError, ApiError)
        assert issubclass(ValidationError, ApiError)
        assert issubclass(RateLimitError, ApiError)
        assert issubclass(ServerError, ApiError)
        assert issubclass(ConnectionError, ApiError)

    def test_api_error_roundtrip(self) -> None:
        exc = ApiError(status_code=500, message="test error")
        assert exc.status_code == 500
        assert exc.message == "test error"
        assert str(exc) == "test error"

    def test_authentication_error_default_code(self) -> None:
        exc = AuthenticationError("invalid key")
        assert exc.status_code == 401
        assert exc.message == "invalid key"

    def test_not_found_error_default_code(self) -> None:
        exc = NotFoundError("not found")
        assert exc.status_code == 404

    def test_validation_error_default_code(self) -> None:
        exc = ValidationError("bad input")
        assert exc.status_code == 422

    def test_rate_limit_error_with_retry_after(self) -> None:
        exc = RateLimitError("too many", retry_after=5.0)
        assert exc.status_code == 429
        assert exc.retry_after == 5.0

    def test_rate_limit_error_without_retry_after(self) -> None:
        exc = RateLimitError("too many")
        assert exc.retry_after is None

    def test_server_error_preserves_message(self) -> None:
        exc = ServerError("Internal server error occurred")
        assert exc.message == "Internal server error occurred"

    def test_connection_error_no_status_code(self) -> None:
        exc = ConnectionError("server unreachable")
        assert exc.status_code is None
        assert exc.message == "server unreachable"

    def test_custom_status_code_override(self) -> None:
        exc = AuthenticationError("custom", status_code=403)
        assert exc.status_code == 403
