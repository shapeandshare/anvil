# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Collision prevention e2e tests.

Verifies that:
- Creating an instance with a port already used by another instance is
  rejected.
- Creating an instance with an overlapping workspace root is rejected.
- Stale workspace locks are reclaimed on instance creation.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from anvil.services.instances.instance_lifecycle_service import InstanceLifecycleService
from anvil.services.instances.workspace_lock import WorkspaceLock

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


@pytest_asyncio.fixture
async def service(
    registry_session: AsyncSession,
) -> InstanceLifecycleService:
    """Build a service wired to the in-memory registry."""
    return InstanceLifecycleService(
        registry_session,
        registry_session=registry_session,
    )


# ── Used port rejection ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_rejects_port_conflict_by_another_instance(
    service: InstanceLifecycleService,
) -> None:
    """Creating an instance on a port already used by another instance
    raises ValueError with a clear error message referencing the owning
    instance.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        ws_a = Path(tmpdir) / "agent-a"
        ws_b = Path(tmpdir) / "agent-b"

        await service.create(
            name="agent-a",
            workspace_root=ws_a,
            web_port=20001,
            mlflow_port=21001,
        )

        with pytest.raises(
            ValueError,
            match="Port 20001 is already in use by instance 'agent-a'",
        ):
            await service.create(
                name="agent-b",
                workspace_root=ws_b,
                web_port=20001,
                mlflow_port=21002,
            )


@pytest.mark.asyncio
async def test_create_rejects_mlflow_port_conflict(
    service: InstanceLifecycleService,
) -> None:
    """Creating an instance on an MLflow port already used by another
    instance raises ValueError.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        ws_a = Path(tmpdir) / "a-ml"
        ws_b = Path(tmpdir) / "b-ml"

        await service.create(
            name="ml-first",
            workspace_root=ws_a,
            web_port=20002,
            mlflow_port=21003,
        )

        with pytest.raises(
            ValueError,
            match="Port 21003 is already in use by instance 'ml-first'",
        ):
            await service.create(
                name="ml-second",
                workspace_root=ws_b,
                web_port=20003,
                mlflow_port=21003,
            )


# ── Workspace overlap rejection ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_rejects_subdirectory_workspace_overlap(
    service: InstanceLifecycleService,
) -> None:
    """Creating an instance with a workspace that is a subdirectory of
    an existing instance's workspace is rejected.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        parent = Path(tmpdir) / "parent-ws"
        await service.create(
            name="parent-instance",
            workspace_root=parent,
            web_port=20004,
            mlflow_port=21004,
        )

        with pytest.raises(ValueError, match="overlaps with"):
            await service.create(
                name="child-instance",
                workspace_root=parent / "sub" / "nested",
                web_port=20005,
                mlflow_port=21005,
            )


@pytest.mark.asyncio
async def test_create_rejects_parent_workspace_overlap(
    service: InstanceLifecycleService,
) -> None:
    """Creating an instance with a workspace that contains an existing
    instance's workspace is rejected.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        child = Path(tmpdir) / "child-data"
        await service.create(
            name="nested-instance",
            workspace_root=child,
            web_port=20006,
            mlflow_port=21006,
        )

        with pytest.raises(ValueError, match="overlaps with"):
            await service.create(
                name="outer-instance",
                workspace_root=Path(tmpdir),
                web_port=20007,
                mlflow_port=21007,
            )


# ── Stale lock reclamation ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_reclaims_stale_lock(
    service: InstanceLifecycleService,
) -> None:
    """Creating an instance reclaims a stale workspace lock (dead PID)
    without error.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir) / "reclaim-ws"
        ws.mkdir(parents=True, exist_ok=True)
        lock_path = ws / ".anvil-lock"
        # Write a PID that almost certainly does not exist.
        lock_path.write_text("2147483646")

        # This should succeed (stale lock is reclaimed during create).
        record = await service.create(
            name="reclaimer",
            workspace_root=ws,
            web_port=20008,
            mlflow_port=21008,
        )
        assert record.name == "reclaimer"


@pytest.mark.asyncio
async def test_create_workspace_lock_is_empty_after_create(
    service: InstanceLifecycleService,
) -> None:
    """After create(), the workspace should not have a live lock
    (create reclaims stale locks but does not acquire a new one).
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir) / "clean-ws"
        record = await service.create(
            name="clean-instance",
            workspace_root=ws,
            web_port=20009,
            mlflow_port=21009,
        )
        assert record.name == "clean-instance"
        lock_path = ws / ".anvil-lock"
        # create() should NOT leave a live lock file.
        assert not lock_path.exists()
