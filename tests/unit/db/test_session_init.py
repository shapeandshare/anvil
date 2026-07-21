"""Unit tests for db/session engine lifecycle.

Verifies that ``async_engine`` is initialised on module import
(backward compat).
"""

from __future__ import annotations


def test_async_engine_initialised_on_import() -> None:
    """Default import path: engine exists and session factory works."""
    from anvil.db.session import AsyncSessionLocal, async_engine

    assert async_engine is not None
    assert AsyncSessionLocal is not None
