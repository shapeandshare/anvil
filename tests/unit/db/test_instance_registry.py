# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for InstanceRegistryRepository CRUD + collision detection.

Each test gets a fresh in-memory SQLite database bound to the global
registry schema, giving complete isolation.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path

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


@pytest.mark.asyncio
async def test_register_creates_row(registry_session: AsyncSession) -> None:
    """Registering an instance record creates a row with an id."""
    repo = InstanceRegistryRepository(registry_session)
    record = InstanceRecord(
        name="test-instance",
        workspace_root="/tmp/anvil-test-1",
        web_port=9090,
        mlflow_port=6001,
    )
    saved = await repo.register(record)
    assert saved.id is not None
    assert saved.name == "test-instance"
    await registry_session.commit()


@pytest.mark.asyncio
async def test_get_by_name_returns_row(registry_session: AsyncSession) -> None:
    """Looking up by name returns the correct record."""
    repo = InstanceRegistryRepository(registry_session)
    record = InstanceRecord(
        name="find-me",
        workspace_root="/tmp/anvil-find",
        web_port=9091,
        mlflow_port=6002,
    )
    await repo.register(record)
    await registry_session.commit()

    found = await repo.get_by_name("find-me")
    assert found is not None
    assert found.workspace_root == "/tmp/anvil-find"


@pytest.mark.asyncio
async def test_get_by_name_returns_none_for_missing(
    registry_session: AsyncSession,
) -> None:
    """Looking up a non-existent name returns None."""
    repo = InstanceRegistryRepository(registry_session)
    found = await repo.get_by_name("does-not-exist")
    assert found is None


@pytest.mark.asyncio
async def test_list_all_returns_all_rows(
    registry_session: AsyncSession,
) -> None:
    """Listing all returns every registered record."""
    repo = InstanceRegistryRepository(registry_session)
    for i in range(3):
        await repo.register(
            InstanceRecord(
                name=f"instance-{i}",
                workspace_root=f"/tmp/anvil-list-{i}",
                web_port=9100 + i,
                mlflow_port=6100 + i,
            )
        )
    await registry_session.commit()

    all_records = await repo.list_all()
    names = {r.name for r in all_records}
    assert names == {"instance-0", "instance-1", "instance-2"}


@pytest.mark.asyncio
async def test_deregister_removes_row(registry_session: AsyncSession) -> None:
    """Deregistering removes the row from the registry."""
    repo = InstanceRegistryRepository(registry_session)
    await repo.register(
        InstanceRecord(
            name="to-delete",
            workspace_root="/tmp/anvil-del",
            web_port=9200,
            mlflow_port=6200,
        )
    )
    await registry_session.commit()

    await repo.deregister("to-delete")
    await registry_session.commit()

    found = await repo.get_by_name("to-delete")
    assert found is None


@pytest.mark.asyncio
async def test_duplicate_name_raises_value_error(
    registry_session: AsyncSession,
) -> None:
    """Registering a duplicate name raises a ValueError collision."""
    repo = InstanceRegistryRepository(registry_session)
    await repo.register(
        InstanceRecord(
            name="unique",
            workspace_root="/tmp/anvil-uniq-1",
            web_port=9300,
            mlflow_port=6300,
        )
    )
    await registry_session.commit()

    with pytest.raises(ValueError, match="already exists"):
        await repo.register(
            InstanceRecord(
                name="unique",
                workspace_root="/tmp/anvil-uniq-2",
                web_port=9301,
                mlflow_port=6301,
            )
        )


@pytest.mark.asyncio
async def test_find_port_conflict_detects_collision(
    registry_session: AsyncSession,
) -> None:
    """find_port_conflict returns a record when a port is taken."""
    repo = InstanceRegistryRepository(registry_session)
    await repo.register(
        InstanceRecord(
            name="port-owner",
            workspace_root="/tmp/anvil-port",
            web_port=9400,
            mlflow_port=6400,
        )
    )
    await registry_session.commit()

    conflict = await repo.find_port_conflict(9400, 9999)
    assert conflict is not None
    assert conflict.name == "port-owner"


@pytest.mark.asyncio
async def test_find_port_conflict_returns_none_when_free(
    registry_session: AsyncSession,
) -> None:
    """find_port_conflict returns None when both ports are free."""
    repo = InstanceRegistryRepository(registry_session)
    conflict = await repo.find_port_conflict(9999, 8888)
    assert conflict is None


@pytest.mark.asyncio
async def test_find_workspace_conflict_detects_collision(
    registry_session: AsyncSession,
) -> None:
    """find_workspace_conflict returns a record when root is taken."""
    repo = InstanceRegistryRepository(registry_session)
    await repo.register(
        InstanceRecord(
            name="ws-owner",
            workspace_root="/tmp/anvil-ws",
            web_port=9500,
            mlflow_port=6500,
        )
    )
    await registry_session.commit()

    conflict = await repo.find_workspace_conflict("/tmp/anvil-ws")
    assert conflict is not None
    assert conflict.name == "ws-owner"


@pytest.mark.asyncio
async def test_find_workspace_conflict_returns_none_when_free(
    registry_session: AsyncSession,
) -> None:
    """find_workspace_conflict returns None when root is free."""
    repo = InstanceRegistryRepository(registry_session)
    conflict = await repo.find_workspace_conflict("/tmp/free-root")
    assert conflict is None


@pytest.mark.asyncio
async def test_list_all_empty_when_no_records(
    registry_session: AsyncSession,
) -> None:
    """list_all returns an empty sequence when nothing is registered."""
    repo = InstanceRegistryRepository(registry_session)
    all_records = await repo.list_all()
    assert len(all_records) == 0
