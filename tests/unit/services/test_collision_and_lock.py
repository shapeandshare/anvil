# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for collision detection and WorkspaceLock.

Covers port collision detection, workspace overlap detection (exact
and sub-path/nesting), and the full WorkspaceLock lifecycle (acquire,
release, reclaim for stale PIDs, refusal for live PIDs).
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncGenerator
from pathlib import Path
from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from anvil.db.repositories.instance_registry import (
    InstanceRegistryRepository,
    _get_instance_model,
)
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


# ── Fixtures ──────────────────────────────────────────────────────────────


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
    """Build an InstanceLifecycleService wired to the in-memory registry."""
    return InstanceLifecycleService(
        registry_session,
        registry_session=registry_session,
    )


@pytest_asyncio.fixture
async def registry(
    registry_session: AsyncSession,
) -> InstanceRegistryRepository:
    """Return an InstanceRegistryRepository bound to the in-memory DB."""
    return InstanceRegistryRepository(registry_session)


# ── Port collision detection ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_find_port_conflict_detects_web_port_collision(
    service: InstanceLifecycleService,
    registry: InstanceRegistryRepository,
) -> None:
    """find_port_conflict detects when web_port matches an existing
    instance's web port.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        await service.create(
            name="agent-a",
            workspace_root=Path(tmpdir) / "a",
            web_port=18080,
            mlflow_port=15001,
        )
        conflict = await registry.find_port_conflict(18080, 99999)
        assert conflict is not None
        assert conflict.name == "agent-a"


@pytest.mark.asyncio
async def test_find_port_conflict_detects_mlflow_port_collision(
    service: InstanceLifecycleService,
    registry: InstanceRegistryRepository,
) -> None:
    """find_port_conflict detects when mlflow_port matches an existing
    instance's mlflow port.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        await service.create(
            name="agent-b",
            workspace_root=Path(tmpdir) / "b",
            web_port=18081,
            mlflow_port=15002,
        )
        conflict = await registry.find_port_conflict(99999, 15002)
        assert conflict is not None
        assert conflict.name == "agent-b"


@pytest.mark.asyncio
async def test_find_port_conflict_returns_none_for_free_ports(
    registry: InstanceRegistryRepository,
) -> None:
    """find_port_conflict returns None when neither port is registered."""
    conflict = await registry.find_port_conflict(99998, 99997)
    assert conflict is None


# ── Workspace exact overlap detection ─────────────────────────────────────


@pytest.mark.asyncio
async def test_find_workspace_conflict_exact_match(
    service: InstanceLifecycleService,
    registry: InstanceRegistryRepository,
) -> None:
    """find_workspace_conflict detects an exact workspace root match."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir) / "exact"
        await service.create(
            name="exact-match",
            workspace_root=ws,
            web_port=18082,
            mlflow_port=15003,
        )
        conflict = await registry.find_workspace_conflict(str(ws.resolve()))
        assert conflict is not None
        assert conflict.name == "exact-match"


# ── Workspace sub-path / nesting detection ────────────────────────────────


@pytest.mark.asyncio
async def test_find_workspace_overlap_detects_subdirectory(
    service: InstanceLifecycleService,
    registry: InstanceRegistryRepository,
) -> None:
    """find_workspace_overlap detects when a workspace is a subdirectory
    of a registered workspace.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        parent = Path(tmpdir) / "parent"
        await service.create(
            name="parent-instance",
            workspace_root=parent,
            web_port=18083,
            mlflow_port=15004,
        )
        child = parent / "sub" / "nested"
        overlap = await registry.find_workspace_overlap(str(child))
        assert overlap is not None
        assert overlap.name == "parent-instance"


@pytest.mark.asyncio
async def test_find_workspace_overlap_detects_parent(
    service: InstanceLifecycleService,
    registry: InstanceRegistryRepository,
) -> None:
    """find_workspace_overlap detects when a registered workspace is a
    subdirectory of the requested workspace.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        child = Path(tmpdir) / "child"
        await service.create(
            name="child-instance",
            workspace_root=child,
            web_port=18084,
            mlflow_port=15005,
        )
        parent = Path(tmpdir)
        overlap = await registry.find_workspace_overlap(str(parent))
        assert overlap is not None
        assert overlap.name == "child-instance"


@pytest.mark.asyncio
async def test_find_workspace_overlap_returns_none_for_disjoint(
    registry: InstanceRegistryRepository,
) -> None:
    """find_workspace_overlap returns None for completely disjoint
    workspaces.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        overlap = await registry.find_workspace_overlap(str(Path(tmpdir) / "disjoint"))
        assert overlap is None


# ── WorkspaceLock: acquire ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_workspace_lock_acquire_creates_lock_file() -> None:
    """WorkspaceLock.acquire() writes a PID file to .anvil-lock."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir)
        lock = WorkspaceLock(ws)
        acquired = await lock.acquire()
        assert acquired is True
        lock_path = ws / ".anvil-lock"
        assert lock_path.exists()
        pid = int(lock_path.read_text().strip())
        assert pid == os.getpid()


@pytest.mark.asyncio
async def test_workspace_lock_acquire_refuses_when_live_pid() -> None:
    """WorkspaceLock.acquire() returns False when lock held by live
    process.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir)
        lock_path = ws / ".anvil-lock"
        # Write our own PID — we are alive.
        lock_path.write_text(str(os.getpid()))

        lock = WorkspaceLock(ws)
        acquired = await lock.acquire()
        assert acquired is False


@pytest.mark.asyncio
async def test_workspace_lock_acquire_reclaims_stale_pid() -> None:
    """WorkspaceLock.acquire() overwrites a stale lock file (dead PID)
    and returns True.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir)
        lock_path = ws / ".anvil-lock"
        # Write a PID that almost certainly does not exist.
        lock_path.write_text("2147483646")

        lock = WorkspaceLock(ws)
        with patch(
            "anvil.services.instances.workspace_lock._pid_alive", return_value=False
        ):
            acquired = await lock.acquire()
        assert acquired is True
        # Lock file now contains our PID.
        pid = int(lock_path.read_text().strip())
        assert pid == os.getpid()


# ── WorkspaceLock: release ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_workspace_lock_release_removes_lock_file() -> None:
    """WorkspaceLock.release() removes the .anvil-lock file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir)
        lock = WorkspaceLock(ws)
        await lock.acquire()
        assert (ws / ".anvil-lock").exists()

        await lock.release()
        assert not (ws / ".anvil-lock").exists()


@pytest.mark.asyncio
async def test_workspace_lock_release_idempotent() -> None:
    """WorkspaceLock.release() is idempotent — no error if lock file
    already missing.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir)
        lock = WorkspaceLock(ws)
        # No lock file exists.
        await lock.release()  # Should not raise.


# ── WorkspaceLock: reclaim ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_workspace_lock_reclaim_removes_stale_lock() -> None:
    """WorkspaceLock.reclaim() removes a stale lock file and returns
    True.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir)
        lock_path = ws / ".anvil-lock"
        lock_path.write_text("2147483646")

        with patch(
            "anvil.services.instances.workspace_lock._pid_alive", return_value=False
        ):
            reclaimed = await WorkspaceLock.reclaim(ws)
        assert reclaimed is True
        assert not lock_path.exists()


@pytest.mark.asyncio
async def test_workspace_lock_reclaim_returns_false_when_pid_alive() -> None:
    """WorkspaceLock.reclaim() returns False when the recorded PID is
    alive.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir)
        lock_path = ws / ".anvil-lock"
        lock_path.write_text(str(os.getpid()))

        with patch(
            "anvil.services.instances.workspace_lock._pid_alive", return_value=True
        ):
            reclaimed = await WorkspaceLock.reclaim(ws)
        assert reclaimed is False
        assert lock_path.exists()


@pytest.mark.asyncio
async def test_workspace_lock_reclaim_returns_false_no_lock_file() -> None:
    """WorkspaceLock.reclaim() returns False when no lock file exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir)
        reclaimed = await WorkspaceLock.reclaim(ws)
        assert reclaimed is False


# ── create() collision checks ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_rejects_port_conflict(
    service: InstanceLifecycleService,
) -> None:
    """create() raises ValueError when another instance uses the same
    port.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        await service.create(
            name="first",
            workspace_root=Path(tmpdir) / "first",
            web_port=19001,
            mlflow_port=19002,
        )
        with pytest.raises(
            ValueError, match="Port 19001 is already in use by instance 'first'"
        ):
            await service.create(
                name="second",
                workspace_root=Path(tmpdir) / "second",
                web_port=19001,
                mlflow_port=19003,
            )


@pytest.mark.asyncio
async def test_create_rejects_workspace_overlap(
    service: InstanceLifecycleService,
) -> None:
    """create() raises ValueError when workspace overlaps with an
    existing instance.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        parent = Path(tmpdir) / "overlap-root"
        await service.create(
            name="overlap-me",
            workspace_root=parent,
            web_port=19004,
            mlflow_port=19005,
        )
        with pytest.raises(ValueError, match="overlaps with"):
            await service.create(
                name="sub-instance",
                workspace_root=parent / "sub",
                web_port=19006,
                mlflow_port=19007,
            )
