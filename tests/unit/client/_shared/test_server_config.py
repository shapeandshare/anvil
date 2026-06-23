# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for ServerConfig — env/arg/default resolution and validation."""

from __future__ import annotations

import os

import pytest
from pydantic import ValidationError as PydanticValidationError

from anvil.client._shared.server_config import ServerConfig


class TestServerConfigDefaults:
    """Default values when no args or env vars are set."""

    def test_defaults(self) -> None:
        config = ServerConfig()
        assert config.base_url == "http://localhost:8080"
        assert config.timeout == 30.0
        assert config.retry_count == 3
        assert config.retry_backoff == 0.5


class TestServerConfigFromEnv:
    """Environment variable resolution via from_env()."""

    def test_from_env_with_explicit_overrides(self) -> None:
        config = ServerConfig.from_env(base_url="http://example.com:9090", timeout=15.0)
        assert config.base_url == "http://example.com:9090"
        assert config.timeout == 15.0

    def test_from_env_reads_env_vars(self) -> None:
        os.environ["ANVIL_SERVER_URL"] = "http://env-test:8080"
        os.environ["ANVIL_TIMEOUT"] = "60"
        try:
            config = ServerConfig.from_env()
            assert config.base_url == "http://env-test:8080"
            assert config.timeout == 60.0
        finally:
            del os.environ["ANVIL_SERVER_URL"]
            del os.environ["ANVIL_TIMEOUT"]

    def test_explicit_arg_overrides_env_var(self) -> None:
        os.environ["ANVIL_SERVER_URL"] = "http://env:8080"
        try:
            config = ServerConfig.from_env(base_url="http://explicit:8080")
            assert config.base_url == "http://explicit:8080"
        finally:
            del os.environ["ANVIL_SERVER_URL"]

    def test_from_env_respects_defaults_when_none_set(self) -> None:
        config = ServerConfig.from_env()
        assert config.base_url == "http://localhost:8080"
        assert config.timeout == 30.0


class TestServerConfigValidation:
    """Pydantic validation on constrained fields."""

    def test_timeout_must_be_positive(self) -> None:
        with pytest.raises(PydanticValidationError):
            ServerConfig(timeout=0)

    def test_timeout_must_be_positive_negative(self) -> None:
        with pytest.raises(PydanticValidationError):
            ServerConfig(timeout=-1)

    def test_retry_count_non_negative(self) -> None:
        with pytest.raises(PydanticValidationError):
            ServerConfig(retry_count=-1)

    def test_retry_backoff_non_negative(self) -> None:
        with pytest.raises(PydanticValidationError):
            ServerConfig(retry_backoff=-0.5)

    def test_base_url_non_empty(self) -> None:
        with pytest.raises(PydanticValidationError):
            ServerConfig(base_url="")
