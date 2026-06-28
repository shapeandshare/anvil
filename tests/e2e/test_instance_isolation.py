# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Multi-process / multi-workspace isolation smoke tests.

Verifies that distinct instances can write distinct data to distinct
workspaces without cross-contamination.  Uses the in-memory registry
and temp directories — no actual subprocesses are started (those are
tested in unit tests with mocks).
"""

from __future__ import annotations

import tempfile
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from anvil.services.instances.instance_lifecycle_service import (
    InstanceLifecycleService,
)

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


def _make_service(
    registry_session: AsyncSession,
) -> InstanceLifecycleService:
    """Build a service wired to the in-memory registry."""
    return InstanceLifecycleService(
        registry_session,
        registry_session=registry_session,
    )


# ── Isolation smoke tests ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_two_instances_have_distinct_workspaces(
    registry_session: AsyncSession,
) -> None:
    """Two created instances get distinct workspace directories with
    no cross-contamination of boot files.
    """
    service = _make_service(registry_session)

    with tempfile.TemporaryDirectory() as tmpdir:
        ws1 = Path(tmpdir) / "apples"
        ws2 = Path(tmpdir) / "oranges"

        rec1 = await service.create(
            name="apples",
            workspace_root=ws1,
            web_port=20001,
            mlflow_port=21001,
        )
        rec2 = await service.create(
            name="oranges",
            workspace_root=ws2,
            web_port=20002,
            mlflow_port=21002,
        )

        # Distinct names and roots.
        assert rec1.name == "apples"
        assert rec2.name == "oranges"
        assert rec1.workspace_root != rec2.workspace_root

        # Each workspace has its own boot file with the correct name.
        boot1 = (ws1 / "instance.json").read_text()
        boot2 = (ws2 / "instance.json").read_text()
        assert "apples" in boot1
        assert "oranges" in boot2
        assert "oranges" not in boot1
        assert "apples" not in boot2

        # Distinct ports.
        assert rec1.web_port != rec2.web_port
        assert rec1.mlflow_port != rec2.mlflow_port


@pytest.mark.asyncio
async def test_registry_lists_all_instances(
    registry_session: AsyncSession,
) -> None:
    """The global registry correctly lists all created instances."""
    service = _make_service(registry_session)

    with tempfile.TemporaryDirectory() as tmpdir:
        for i in range(3):
            await service.create(
                name=f"multi-{i}",
                workspace_root=Path(tmpdir) / f"ws-{i}",
                web_port=21000 + i,
                mlflow_port=22000 + i,
            )

        repo = await service.get_registry()
        all_records = await repo.list_all()
        names = [r.name for r in all_records]
        assert "multi-0" in names
        assert "multi-1" in names
        assert "multi-2" in names
        assert len(names) >= 3


@pytest.mark.asyncio
async def test_collision_detection_across_instances(
    registry_session: AsyncSession,
) -> None:
    """Creating an instance with a colliding name is rejected."""
    service = _make_service(registry_session)

    with tempfile.TemporaryDirectory() as tmpdir:
        ws1 = Path(tmpdir) / "collision-1"
        ws2 = Path(tmpdir) / "collision-2"

        await service.create(
            name="collide-me",
            workspace_root=ws1,
            web_port=22001,
            mlflow_port=23001,
        )

        with pytest.raises(ValueError, match="already exists"):
            await service.create(
                name="collide-me",
                workspace_root=ws2,
                web_port=22002,
                mlflow_port=23002,
            )


@pytest.mark.asyncio
async def test_deregister_isolates_remaining_instances(
    registry_session: AsyncSession,
) -> None:
    """Deregistering one instance does not affect the registry entry
    of another.
    """
    service = _make_service(registry_session)

    with tempfile.TemporaryDirectory() as tmpdir:
        ws1 = Path(tmpdir) / "keep"
        ws2 = Path(tmpdir) / "remove"

        await service.create(
            name="keep-me",
            workspace_root=ws1,
            web_port=23001,
            mlflow_port=24001,
        )
        await service.create(
            name="remove-me",
            workspace_root=ws2,
            web_port=23002,
            mlflow_port=24002,
        )

        repo = await service.get_registry()
        await repo.deregister("remove-me")
        await registry_session.commit()

        remaining = await repo.list_all()
        names = [r.name for r in remaining]
        assert "keep-me" in names
        assert "remove-me" not in names


# ── Parametrized smoke: ≥10 instances ────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("i", list(range(10)))
async def test_parametrized_smoke_ten_instances(
    i: int,
    registry_session: AsyncSession,
) -> None:
    """Create 10 distinct instances (parametrized), each in its own
    temp workspace.  Verifies distinct workspace roots and names.
    """
    service = _make_service(registry_session)

    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir) / f"smoke-{i}"
        rec = await service.create(
            name=f"smoke-{i}",
            workspace_root=ws,
            web_port=30000 + i,
            mlflow_port=31000 + i,
        )
        assert rec.name == f"smoke-{i}"
        assert str(rec.workspace_root).endswith(f"smoke-{i}")
        assert (ws / "instance.json").exists()

        # Verify boot file content is correct for this instance.
        boot = (ws / "instance.json").read_text()
        assert rec.name in boot