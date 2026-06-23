# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Server connection configuration for the anvil client SDK.

``ServerConfig`` resolves connection parameters from explicit arguments,
environment variables, or built-in defaults — in that priority order.
"""

from __future__ import annotations

import os

from pydantic import BaseModel, field_validator


class ServerConfig(BaseModel):
    """Connection and retry configuration for the anvil server.

    Parameters
    ----------
    base_url : str
        Base URL of the anvil server. Defaults to ``"http://localhost:8080"``.
    timeout : float
        Request timeout in seconds. Must be greater than 0.
        Defaults to ``30.0``.
    retry_count : int
        Maximum number of retry attempts for failed requests.
        Must be >= 0. Defaults to ``3``.
    retry_backoff : float
        Base backoff factor in seconds between retries.
        Must be >= 0. Defaults to ``0.5``.
    """

    base_url: str = "http://localhost:8080"
    timeout: float = 30.0
    retry_count: int = 3
    retry_backoff: float = 0.5

    # --- validators -----------------------------------------------------------

    @field_validator("timeout")
    @classmethod
    def _validate_timeout(cls, v: float) -> float:
        """Ensure timeout is positive."""
        if v <= 0:
            raise ValueError("timeout must be greater than 0")
        return v

    @field_validator("retry_count")
    @classmethod
    def _validate_retry_count(cls, v: int) -> int:
        """Ensure retry count is non-negative."""
        if v < 0:
            raise ValueError("retry_count must be >= 0")
        return v

    @field_validator("retry_backoff")
    @classmethod
    def _validate_retry_backoff(cls, v: float) -> float:
        """Ensure retry backoff is non-negative."""
        if v < 0:
            raise ValueError("retry_backoff must be >= 0")
        return v

    @field_validator("base_url")
    @classmethod
    def _validate_base_url(cls, v: str) -> str:
        """Ensure base URL is non-empty."""
        if not v:
            raise ValueError("base_url must not be empty")
        return v

    # --- factory --------------------------------------------------------------

    @classmethod
    def from_env(
        cls,
        base_url: str | None = None,
        timeout: float | None = None,
        retry_count: int | None = None,
        retry_backoff: float | None = None,
    ) -> ServerConfig:
        """Build a ``ServerConfig`` from explicit arguments, environment
        variables, or built-in defaults — in that priority order.

        Resolves each field by checking, in order:
        1. Explicit keyword argument (highest priority)
        2. Corresponding environment variable
        3. Class-level default (lowest priority)

        Environment variables
        ---------------------
        ANVIL_SERVER_URL : str
            Override for ``base_url``.
        ANVIL_TIMEOUT : str
            Override for ``timeout`` (parsed as ``float``).
        ANVIL_RETRY_COUNT : str
            Override for ``retry_count`` (parsed as ``int``).
        ANVIL_RETRY_BACKOFF : str
            Override for ``retry_backoff`` (parsed as ``float``).

        Parameters
        ----------
        base_url : str | None
            Explicit base URL override.
        timeout : float | None
            Explicit timeout override.
        retry_count : int | None
            Explicit retry count override.
        retry_backoff : float | None
            Explicit retry backoff override.

        Returns
        -------
        ServerConfig
            Resolved configuration instance.
        """
        resolved = cls()

        if base_url is not None:
            resolved.base_url = base_url
        elif os.environ.get("ANVIL_SERVER_URL"):
            resolved.base_url = os.environ["ANVIL_SERVER_URL"]

        if timeout is not None:
            resolved.timeout = timeout
        elif os.environ.get("ANVIL_TIMEOUT"):
            resolved.timeout = float(os.environ["ANVIL_TIMEOUT"])

        if retry_count is not None:
            resolved.retry_count = retry_count
        elif os.environ.get("ANVIL_RETRY_COUNT"):
            resolved.retry_count = int(os.environ["ANVIL_RETRY_COUNT"])

        if retry_backoff is not None:
            resolved.retry_backoff = retry_backoff
        elif os.environ.get("ANVIL_RETRY_BACKOFF"):
            resolved.retry_backoff = float(os.environ["ANVIL_RETRY_BACKOFF"])

        return resolved
