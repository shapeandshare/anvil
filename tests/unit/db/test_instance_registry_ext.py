# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Extends InstanceRegistryRepository tests to cover missing lines.

Tests unique-constraint violations for workspace_root, web_port, and
mlflow_port; find_workspace_overlap (subdirectory checks); idempotent
deregister on a non-existent name; and find_port_conflict for the
mlflow_port path.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from anvil.db.models.instance_record import InstanceRecord
from anvil.db.repositories.instance_registry import InstanceRegistryRepository

# Must match the DDL in instance_registry.py.
_CREATE_TABLE_SQL: str = """\
CREATE TABLE IF NOT EXISTS instance_records (
    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    workspace_root VARCHAR(500) NOT NULL,
    web_port INTEGER NOT NULL,
    mlflow_port INTEGER NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (name),
    UNIQUE (workspace_root),
    UNIQUE (web_port),
    UNIQUE (mlflow_port)
)
"""


@pytest_asyncio.fixture
async def registry_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh in-memory registry DB per test."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.execute(text(_CREATE_TABLE_SQL))
        await conn.commit()

    factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with factory() as session:
        yield session

    await engine.dispose()


def _record(
    name: str = "test",
    workspace_root: str = "/tmp/anvil-test",
    web_port: int = 9090,
    mlflow_port: int = 6001,
) -> InstanceRecord:
    """Build an InstanceRecord with overridable defaults."""
    return InstanceRecord(
        name=name,
        workspace_root=workspace_root,
        web_port=web_port,
        mlflow_port=mlflow_port,
    )


# ── Unique constraint violations ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_duplicate_workspace_root_raises_value_error(
    registry_session: AsyncSession,
) -> None:
    """Registering a duplicate workspace_root raises ValueError.

    Note: The production code's ``register()`` checks ``record.name in err_msg``
    or ``"name" in err_msg`` first.  Because the SQL error text contains the
    string "name" (from column names in the SQL statement), the name-match
    branch fires before the workspace_root branch.  This test documents that
    behaviour — the ValueError message mentions the second record's name
    rather than the workspace_root.
    """
    repo = InstanceRegistryRepository(registry_session)
    await repo.register(_record(name="one", workspace_root="/same/path"))
    await registry_session.commit()

    with pytest.raises(ValueError, match="already exists"):
        await repo.register(_record(name="two", workspace_root="/same/path"))


@pytest.mark.asyncio
async def test_duplicate_web_port_raises_value_error(
    registry_session: AsyncSession,
) -> None:
    """Registering a duplicate web_port raises ValueError.

    The name-match branch fires first (see workspace_root test note).
    """
    repo = InstanceRegistryRepository(registry_session)
    await repo.register(_record(name="a", web_port=8080))
    await registry_session.commit()

    with pytest.raises(ValueError, match="already exists"):
        await repo.register(_record(name="b", workspace_root="/other", web_port=8080))


@pytest.mark.asyncio
async def test_duplicate_mlflow_port_raises_value_error(
    registry_session: AsyncSession,
) -> None:
    """Registering a duplicate mlflow_port raises ValueError.

    The name-match branch fires first (see workspace_root test note).
    """
    repo = InstanceRegistryRepository(registry_session)
    await repo.register(_record(name="x", mlflow_port=5001))
    await registry_session.commit()

    with pytest.raises(ValueError, match="already exists"):
        await repo.register(
            _record(name="y", workspace_root="/other2", web_port=9099, mlflow_port=5001)
        )


# ── find_port_conflict (mlflow_port path) ──────────────────────────────────


@pytest.mark.asyncio
async def test_find_port_conflict_mlflow_port(
    registry_session: AsyncSession,
) -> None:
    """find_port_conflict returns a record when mlflow_port is taken."""
    repo = InstanceRegistryRepository(registry_session)
    await repo.register(_record(name="mowner", mlflow_port=7000))
    await registry_session.commit()

    conflict = await repo.find_port_conflict(9999, 7000)
    assert conflict is not None
    assert conflict.name == "mowner"


# ── find_workspace_overlap ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_find_workspace_overlap_exact_match(
    registry_session: AsyncSession,
) -> None:
    """find_workspace_overlap returns a record on exact root match."""
    repo = InstanceRegistryRepository(registry_session)
    await repo.register(_record(name="overlap-me", workspace_root="/app/ws"))
    await registry_session.commit()

    result = await repo.find_workspace_overlap("/app/ws")
    assert result is not None
    assert result.name == "overlap-me"


@pytest.mark.asyncio
async def test_find_workspace_overlap_subdirectory(
    registry_session: AsyncSession,
) -> None:
    """find_workspace_overlap matches when root is a subdirectory
    of an existing workspace_root."""
    repo = InstanceRegistryRepository(registry_session)
    await repo.register(_record(name="parent", workspace_root="/app/ws"))
    await registry_session.commit()

    result = await repo.find_workspace_overlap("/app/ws/subdir")
    assert result is not None
    assert result.name == "parent"


@pytest.mark.asyncio
async def test_find_workspace_overlap_parent_directory(
    registry_session: AsyncSession,
) -> None:
    """find_workspace_overlap matches when an existing record is a
    subdirectory of root."""
    repo = InstanceRegistryRepository(registry_session)
    await repo.register(_record(name="child", workspace_root="/app/ws/subdir"))
    await registry_session.commit()

    result = await repo.find_workspace_overlap("/app/ws")
    assert result is not None
    assert result.name == "child"


@pytest.mark.asyncio
async def test_find_workspace_overlap_no_match(
    registry_session: AsyncSession,
) -> None:
    """find_workspace_overlap returns None when no overlap exists."""
    repo = InstanceRegistryRepository(registry_session)
    await repo.register(_record(name="isolated", workspace_root="/app/ws-a"))
    await registry_session.commit()

    result = await repo.find_workspace_overlap("/app/ws-b")
    assert result is None


@pytest.mark.asyncio
async def test_find_workspace_overlap_empty_registry(
    registry_session: AsyncSession,
) -> None:
    """find_workspace_overlap returns None from an empty registry."""
    repo = InstanceRegistryRepository(registry_session)
    result = await repo.find_workspace_overlap("/any/path")
    assert result is None


# ── deregister idempotent ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_deregister_non_existent_is_idempotent(
    registry_session: AsyncSession,
) -> None:
    """Deregistering a name that does not exist does not raise."""
    repo = InstanceRegistryRepository(registry_session)
    await repo.deregister("never-registered")
    await registry_session.commit()
    # No exception is the pass condition.


# ── register raises generic SQLAlchemyError ────────────────────────────────
#
# NOTE: This deliberately mocks a non-unique SQLAlchemyError to test
# the re-raise path in register().  We patch the session's flush
# method so it raises the correct exception type but with a message
# that does NOT match any of the unique/integrity patterns.


@pytest.mark.asyncio
async def test_register_non_unique_error_re_raises(
    registry_session: AsyncSession,
) -> None:
    """A SQLAlchemyError that is not unique/integrity is re-raised."""
    from sqlalchemy.exc import SQLAlchemyError

    repo = InstanceRegistryRepository(registry_session)

    original_flush = registry_session.flush

    async def _failing_flush() -> None:
        raise SQLAlchemyError("disk full")

    registry_session.flush = _failing_flush  # type: ignore[method-assign]

    with pytest.raises(SQLAlchemyError):
        await repo.register(_record(name="fail-me"))

    registry_session.flush = original_flush  # type: ignore[method-assign]
