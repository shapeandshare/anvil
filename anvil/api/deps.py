# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""FastAPI dependency injection.

Provides reusable FastAPI dependencies such as database session access
and a session-bound :class:`AnvilWorkbench`. Dependencies are consumed
by route handlers via ``Depends()``.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_db
from ..workbench import AnvilWorkbench
from .api_key_store import ApiKeyStore
from .auth import SESSION_COOKIE_NAME

# Import get_db_session for downstream convenience.
__all__ = ["get_actor_from_request", "get_db_session", "get_workbench"]

# Module-level singleton for the API key store — initialised once at
# import time (which happens during application startup).
_api_key_store = ApiKeyStore()


def get_api_key_store() -> ApiKeyStore:
    """Return the application-wide API key store singleton.

    Returns
    -------
    ApiKeyStore
    """
    return _api_key_store


def get_actor_from_request(request: Request) -> str:
    """Extract the authenticated actor identity from a request.

    In local-mode anvil there is no multi-user model: authentication is
    either an API key (shared secret) or a session cookie (random token
    per browser session).  The most stable, non-secret identity available
    is therefore:

    - ``"api_key"`` — when the request carries a valid ``X-API-Key`` header.
    - ``"session:<first-8-chars>"`` — when the request carries a session
      cookie.  The first 8 characters of the session token act as a
      short fingerprint that identifies the session without exposing the
      full token in the audit log.
    - ``"anonymous"`` — fallback when neither credential is present (e.g.
      exempt routes, OPTIONS pre-flight).

    This function is intentionally read-only: it does **not** re-validate
    the credentials.  Auth middleware has already accepted the request by
    the time a route handler runs.

    Parameters
    ----------
    request : Request
        The incoming FastAPI/Starlette request.

    Returns
    -------
    str
        A stable, non-secret actor identifier for use in audit records.
    """
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return "api_key"

    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id:
        # Use a short fingerprint — never log the full session token.
        return f"session:{session_id[:8]}"

    return "anonymous"


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    """Provide an async SQLAlchemy session as a FastAPI dependency.

    Yields an ``AsyncSession`` from the global engine, one per request.
    The caller is responsible for committing or rolling back the session.

    Yields
    ------
    AsyncSession
        An async SQLAlchemy session bound to the application engine.
    """
    async for session in get_db():
        yield session


async def get_workbench() -> AsyncGenerator[AnvilWorkbench]:
    """Provide a session-bound ``AnvilWorkbench`` as a FastAPI dependency.

    Yields a new :class:`AnvilWorkbench` bound to a request-scoped
    ``AsyncSession``.  Services obtained from the workbench share this
    session, so audit writes, provenance updates, etc. participate in
    the same transaction (FR-011).

    Yields
    ------
    AnvilWorkbench
        A workbench instance ready to serve the current request.
    """
    async for session in get_db():
        yield AnvilWorkbench(session)
