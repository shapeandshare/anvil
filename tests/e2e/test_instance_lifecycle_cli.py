# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""End-to-end tests for the instance lifecycle CLI commands.

Exercises the full create -> start -> list -> stop -> destroy flow
using direct service calls (consistent with existing e2e isolation
tests).  Ports are pinned to avoid collisions; subprocess operations
(start/stop) are mocked to keep the test fast and deterministic.
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

from anvil.services.instances.instance_lifecycle_service import InstanceLifecycleService
from anvil.services.instances.instance_status import InstanceStatus

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


# ── Full create → start → list → stop → destroy flow ────────────────────


@pytest.mark.asyncio
async def test_create_start_list_stop_destroy_flow(
    registry_session: AsyncSession,
) -> None:
    """Exercise the full lifecycle: create -> start -> list shows
    running -> stop -> list shows stopped -> destroy -> list empty.
    """
    service = _make_service(registry_session)

    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir) / "e2e-flow"

        # Create.
        rec = await service.create(
            name="e2e-flow-instance",
            workspace_root=ws,
            web_port=19501,
            mlflow_port=19601,
        )
        assert rec.name == "e2e-flow-instance"
        assert ws.exists()

        # List shows created instance with stopped status.
        items = await service.list()
        assert len(items) == 1
        assert items[0]["name"] == "e2e-flow-instance"
        assert items[0]["status"] == InstanceStatus.STOPPED.value

        # Start (mocked).
        pid_path = ws / "logs" / "web.pid"
        with (
            patch(
                "anvil.services.instances.instance_lifecycle_service._is_port_free",
                return_value=True,
            ) as _mock_port,
            patch(
                "anvil.services.instances.instance_lifecycle_service.subprocess.Popen"
            ) as mock_popen,
        ):
            mock_proc = mock_popen.return_value
            mock_proc.pid = 88888
            await service.start("e2e-flow-instance")

        assert pid_path.exists()
        assert int(pid_path.read_text().strip()) == 88888

        # List shows running (mock _process_exists so status()
        # recognises the PID as alive).
        with patch(
            "anvil.services.instances.instance_lifecycle_service._process_exists",
            return_value=True,
        ):
            items = await service.list()
        assert len(items) == 1
        assert items[0]["name"] == "e2e-flow-instance"
        assert items[0]["status"] == InstanceStatus.RUNNING.value

        # Stop (mocked - process exists then disappears).
        with (
            patch(
                "anvil.services.instances.instance_lifecycle_service._process_exists",
                side_effect=[True, False],
            ),
            patch("os.kill"),
        ):
            await service.stop("e2e-flow-instance")

        assert not pid_path.exists()

        # List shows stopped.
        items = await service.list()
        assert len(items) == 1
        assert items[0]["name"] == "e2e-flow-instance"
        assert items[0]["status"] == InstanceStatus.STOPPED.value

        # Destroy.
        await service.destroy("e2e-flow-instance", confirmed=True)
        await registry_session.commit()

        assert not ws.exists()

        # List empty.
        items = await service.list()
        assert len(items) == 0


# ── List with --json shape (dict shape, serializable) ────────────────────


@pytest.mark.asyncio
async def test_list_returns_json_serializable_shape(
    registry_session: AsyncSession,
) -> None:
    """list() returns dicts with all string/int values for JSON
    serialisation.
    """
    service = _make_service(registry_session)

    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir) / "json-shape"
        await service.create(
            name="json-test",
            workspace_root=ws,
            web_port=19502,
            mlflow_port=19602,
        )

        items = await service.list()
        assert len(items) == 1
        entry = items[0]

        # Verify all values are JSON-serialisable types.
        assert isinstance(entry["name"], str)
        assert isinstance(entry["workspace_root"], str)
        assert isinstance(entry["web_port"], int)
        assert isinstance(entry["mlflow_port"], int)
        assert isinstance(entry["status"], str)

        # Round-trip through JSON.
        import json

        serialised = json.dumps(entry)
        deserialised = json.loads(serialised)
        assert deserialised["name"] == "json-test"
        assert deserialised["web_port"] == 19502
        assert deserialised["status"] == "stopped"


# ── Destroy with --keep-data preserves workspace ─────────────────────────


@pytest.mark.asyncio
async def test_destroy_with_keep_data(
    registry_session: AsyncSession,
) -> None:
    """destroy(keep_data=True) preserves workspace but deregisters."""
    service = _make_service(registry_session)

    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir) / "keep-e2e"
        await service.create(
            name="keep-e2e",
            workspace_root=ws,
            web_port=19503,
            mlflow_port=19603,
        )

        await service.destroy("keep-e2e", keep_data=True, confirmed=True)
        await registry_session.commit()

        # Workspace still exists.
        assert ws.exists()
        assert (ws / "instance.json").exists()

        # Deregistered.
        repo = await service.get_registry()
        record = await repo.get_by_name("keep-e2e")
        assert record is None


# ── Destroy without --yes (confirmed=False) is rejected ──────────────────


@pytest.mark.asyncio
async def test_destroy_requires_confirmation(
    registry_session: AsyncSession,
) -> None:
    """destroy() without confirmed=True raises ValueError."""
    service = _make_service(registry_session)

    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir) / "no-yes"
        await service.create(
            name="no-yes",
            workspace_root=ws,
            web_port=19504,
            mlflow_port=19604,
        )

        with pytest.raises(ValueError, match="confirmation"):
            await service.destroy("no-yes", confirmed=False)


# ── Destroy with --force stops running instance ──────────────────────────


@pytest.mark.asyncio
async def test_destroy_with_force(
    registry_session: AsyncSession,
) -> None:
    """destroy(force=True) stops and destroys a running instance."""
    service = _make_service(registry_session)

    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir) / "force-e2e"
        await service.create(
            name="force-e2e",
            workspace_root=ws,
            web_port=19505,
            mlflow_port=19605,
        )

        # Simulate running.
        pid_path = ws / "logs" / "web.pid"
        pid_path.parent.mkdir(parents=True, exist_ok=True)
        pid_path.write_text("99999")

        # Refuse without force (mock _process_exists so destroy
        # sees the instance as RUNNING).
        with patch(
            "anvil.services.instances.instance_lifecycle_service._process_exists",
            return_value=True,
        ):
            with pytest.raises(RuntimeError, match="running"):
                await service.destroy("force-e2e", confirmed=True)

        # Force stop and destroy (mock os.kill to avoid killing a
        # real process).
        with (
            patch(
                "anvil.services.instances.instance_lifecycle_service._process_exists",
                return_value=False,
            ),
            patch("os.kill"),
        ):
            await service.destroy("force-e2e", force=True, confirmed=True)

        await registry_session.commit()

        assert not ws.exists()
        repo = await service.get_registry()
        record = await repo.get_by_name("force-e2e")
        assert record is None


# ── Status transitions through lifecycle ─────────────────────────────────


@pytest.mark.asyncio
async def test_status_transitions(
    registry_session: AsyncSession,
) -> None:
    """status() returns correct status through the lifecycle:
    stopped -> running -> stopped.
    """
    service = _make_service(registry_session)

    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir) / "transitions"
        await service.create(
            name="transition-test",
            workspace_root=ws,
            web_port=19506,
            mlflow_port=19606,
        )

        # After create -> stopped.
        assert await service.status("transition-test") == InstanceStatus.STOPPED

        # After start -> running.
        pid_path = ws / "logs" / "web.pid"
        with (
            patch(
                "anvil.services.instances.instance_lifecycle_service._is_port_free",
                return_value=True,
            ),
            patch(
                "anvil.services.instances.instance_lifecycle_service.subprocess.Popen"
            ) as mock_popen,
        ):
            mock_proc = mock_popen.return_value
            mock_proc.pid = 77777
            await service.start("transition-test")

        # After start -> running (mock _process_exists so status
        # recognises the PID as alive).
        with patch(
            "anvil.services.instances.instance_lifecycle_service._process_exists",
            return_value=True,
        ):
            assert await service.status("transition-test") == InstanceStatus.RUNNING

        # After stop -> stopped.
        with (
            patch(
                "anvil.services.instances.instance_lifecycle_service._process_exists",
                side_effect=[True, False],
            ),
            patch("os.kill"),
        ):
            await service.stop("transition-test")

        assert await service.status("transition-test") == InstanceStatus.STOPPED
