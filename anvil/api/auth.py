# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Authentication primitives — session store, CSRF tokens, and auth helpers.

Provides the in-memory session store, CSRF token generation/validation
using HMAC-SHA256, and support functions consumed by the auth middleware
in :mod:`anvil.api.app`.

Sessions are stored in-process (acceptable for single-process local-first
deployment).  The session ID is delivered as an ``HttpOnly; SameSite=Strict``
cookie named ``anvil_session``.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import time

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------

SESSION_COOKIE_NAME = "anvil_session"
"""str: Name of the HttpOnly session cookie."""

SESSION_TTL_SECONDS = 86_400
"""int: Session lifetime in seconds (24 hours), sliding on each request."""

CSRF_HMAC_KEY = hashlib.sha256(secrets.token_bytes(32)).digest()
"""bytes: Server-side secret key for HMAC-based CSRF token signing.
Generated once at startup."""

# ------------------------------------------------------------------
# Session store
# ------------------------------------------------------------------


class SessionStore:
    """In-memory session store with automatic expiry.

    Sessions are keyed by a random 32-byte session ID.  Each entry
    records the creation time and last-access time for sliding expiry.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, float] = {}  # session_id -> last_access_time

    def create(self) -> str:
        """Create a new session and return its ID.

        Returns
        -------
        str
            A new URL-safe session ID string.
        """
        session_id = secrets.token_urlsafe(32)
        now = time.time()
        self._sessions[session_id] = now
        return session_id

    def validate(self, session_id: str) -> bool:
        """Check whether *session_id* is valid and not expired.

        Touches the session (sliding expiry) on success.

        Parameters
        ----------
        session_id : str
            The session ID to validate.

        Returns
        -------
        bool
            ``True`` if the session exists and is within the TTL window.
        """
        last_access = self._sessions.get(session_id)
        if last_access is None:
            return False
        if time.time() - last_access > SESSION_TTL_SECONDS:
            self._sessions.pop(session_id, None)
            return False
        self._sessions[session_id] = time.time()  # sliding touch
        return True

    def delete(self, session_id: str) -> None:
        """Remove a session (logout).

        Parameters
        ----------
        session_id : str
            The session ID to remove.
        """
        self._sessions.pop(session_id, None)

    def sweep(self) -> int:
        """Remove all expired sessions.

        Returns
        -------
        int
            Number of sessions removed.
        """
        now = time.time()
        expired = [
            sid for sid, ts in self._sessions.items() if now - ts > SESSION_TTL_SECONDS
        ]
        for sid in expired:
            self._sessions.pop(sid, None)
        return len(expired)


# Module-level singleton
_session_store = SessionStore()


def get_session_store() -> SessionStore:
    """Return the application-wide session store singleton.

    Returns
    -------
    SessionStore
    """
    return _session_store


# ------------------------------------------------------------------
# CSRF token helpers (FR-027)
# ------------------------------------------------------------------


def generate_csrf_token(session_id: str) -> str:
    """Generate an HMAC-SHA256 CSRF token bound to *session_id*.

    Parameters
    ----------
    session_id : str
        The session ID to bind the token to.

    Returns
    -------
    str
        Hex-encoded HMAC signature.
    """
    return hmac.new(CSRF_HMAC_KEY, session_id.encode(), "sha256").hexdigest()


def verify_csrf_token(session_id: str, token: str) -> bool:
    """Verify an HMAC-SHA256 CSRF token against *session_id*.

    Uses :func:`secrets.compare_digest` for constant-time comparison.

    Parameters
    ----------
    session_id : str
        The session ID to verify against.
    token : str
        The CSRF token to verify.

    Returns
    -------
    bool
        ``True`` if the token is valid for the given session.
    """
    expected = generate_csrf_token(session_id)
    return secrets.compare_digest(expected, token)


# ------------------------------------------------------------------
# Page-route registry (used by auth middleware)
# ------------------------------------------------------------------

PAGE_ROUTES: frozenset[str] = frozenset(
    {
        "/",
        "/login",
    }
)
"""Set of exact-match HTML page routes that require a session cookie."""

PAGE_PREFIXES: tuple[str, ...] = (
    "/v1/datasets-page",
    "/v1/training-page",
    "/v1/experiments-page",
    "/v1/models-page",
    "/v1/inference-page",
    "/v1/operations-page",
    "/v1/learn",
    "/v1/about",
)
"""Prefixes for HTML page routes (sub-paths under these are also pages)."""

EXEMPT_ROUTES: frozenset[str] = frozenset(
    {
        "/login",
        "/v1/health",
    }
)
"""Routes that are always accessible without authentication."""

EXEMPT_PREFIXES: tuple[str, ...] = ("/static",)
"""Prefixes whose sub-paths are always accessible without authentication."""


def is_page_route(path: str) -> bool:
    """Check whether *path* is a known HTML page route.

    Parameters
    ----------
    path : str
        The URL path to check.

    Returns
    -------
    bool
    """
    if path in PAGE_ROUTES:
        return True
    for prefix in PAGE_PREFIXES:
        if path.startswith(prefix):
            return True
    return False


def is_exempt_route(path: str) -> bool:
    """Check whether *path* is an auth-exempt route.

    Parameters
    ----------
    path : str
        The URL path to check.

    Returns
    -------
    bool
    """
    if path in EXEMPT_ROUTES:
        return True
    for prefix in EXEMPT_PREFIXES:
        if path.startswith(prefix):
            return True
    return False


# ------------------------------------------------------------------
# Middleware-route registry helpers
# ------------------------------------------------------------------

CSRF_EXEMPT_PREFIXES: tuple[str, ...] = ("/v1/mlflow-proxy",)
"""Prefixes that are exempt from the CSRF synchronizer-token check.

``/v1/mlflow-proxy`` is exempt because the embedded MLflow SPA makes
its own state-changing AJAX calls that cannot carry anvil's CSRF token.
Safety relies on ``SameSite=Strict`` + same-origin (FR-027/FR-004).
"""


def is_csrf_exempt(path: str) -> bool:
    """Check whether *path* is exempt from the CSRF token check.

    Parameters
    ----------
    path : str
        The URL path to check.

    Returns
    -------
    bool
    """
    for prefix in CSRF_EXEMPT_PREFIXES:
        if path.startswith(prefix):
            return True
    return False
