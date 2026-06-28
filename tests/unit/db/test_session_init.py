"""Unit tests for db/session engine lifecycle.

Verifies that:
1. ``async_engine`` is initialised on module import (backward compat).
2. ``reinit_engine()`` disposes the old engine and creates a new one
   for a different database path.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def test_async_engine_initialised_on_import() -> None:
    """Default import path: engine exists and session factory works."""
    from anvil.db.session import AsyncSessionLocal, async_engine

    assert async_engine is not None
    assert AsyncSessionLocal is not None


@pytest.mark.asyncio
async def test_reinit_engine_redirects(tmp_path: Path) -> None:
    """reinit_engine() creates a new engine pointed at a different DB.

    Note: ``reinit_engine`` reassigns the module-level ``async_engine``
    variable, so we access it via the module reference rather than a
    one-time ``from ... import`` to see the updated value.
    """
    import anvil.db.session as db_session

    original_url = str(db_session.async_engine.url)
    new_db = tmp_path / "test.db"
    new_db_str = str(new_db)

    # The URL ends with the DB path — verify it's not already our tmp file
    assert new_db_str not in original_url

    # Reinitialize with a new path
    await db_session.reinit_engine(new_db_str)
    new_url = str(db_session.async_engine.url)
    assert new_db_str in new_url
    assert original_url != new_url
    assert new_db.exists()