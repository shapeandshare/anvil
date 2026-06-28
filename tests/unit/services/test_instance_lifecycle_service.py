# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for InstanceLifecycleService — create, start, stop, status.

Uses an in-memory registry DB and mock subprocess for start/stop to
keep tests fast and isolated.
"""

from __future__ import annotations

import os
import signal
import tempfile
from collections.abc import AsyncGenerator
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from anvil.db.repositories.instance_registry import InstanceRegistryRepository
from anvil.services.instances.instance_lifecycle_service import InstanceLifecycleService
from anvil.services.instances.instance_status import InstanceStatus

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


@pytest_asyncio.fixture
async def service(registry_session: AsyncSession) -> InstanceLifecycleService:
    """Build an InstanceLifecycleService wired to the in-memory registry."""
    return InstanceLifecycleService(
        registry_session,
        registry_session=registry_session,
    )


# ── create ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_creates_workspace_and_boot_file(
    service: InstanceLifecycleService,
) -> None:
    """create() creates the workspace dir and writes instance.json."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ws_root = Path(tmpdir) / "test-ws"
        record = await service.create(
            name="create-test",
            workspace_root=ws_root,
            web_port=18080,
            mlflow_port=15001,
        )
        assert record.name == "create-test"
        assert record.web_port == 18080

        # Verify workspace structure was created.
        assert ws_root.exists()
        assert (ws_root / "data").exists()
        assert (ws_root / "logs").exists()
        assert (ws_root / "instance.json").exists()

        # Verify boot config.
        boot_json = (ws_root / "instance.json").read_text()
        assert "create-test" in boot_json
        assert "18080" in boot_json


@pytest.mark.asyncio
async def test_create_auto_allocates_ports(
    service: InstanceLifecycleService,
) -> None:
    """create() auto-allocates ports when none are specified."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ws_root = Path(tmpdir) / "auto-port"
        record = await service.create(
            name="auto-port-test",
            workspace_root=ws_root,
        )
        assert record.web_port > 0
        assert record.mlflow_port > 0


@pytest.mark.asyncio
async def test_create_rejects_invalid_name(
    service: InstanceLifecycleService,
) -> None:
    """create() raises ValueError for invalid names."""
    with tempfile.TemporaryDirectory() as tmpdir:
        for bad_name in ["with space", "has/slash", "has.dot", ""]:
            with pytest.raises(ValueError, match="Invalid instance name"):
                await service.create(
                    name=bad_name,
                    workspace_root=Path(tmpdir) / bad_name,
                )


@pytest.mark.asyncio
async def test_create_duplicate_name_raises(
    service: InstanceLifecycleService,
    registry_session: AsyncSession,
) -> None:
    """create() raises ValueError when name collides."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ws1 = Path(tmpdir) / "dup-1"
        await service.create(
            name="duplicate-me",
            workspace_root=ws1,
            web_port=18081,
            mlflow_port=15002,
        )

        ws2 = Path(tmpdir) / "dup-2"
        with pytest.raises(ValueError, match="already exists"):
            await service.create(
                name="duplicate-me",
                workspace_root=ws2,
                web_port=18082,
                mlflow_port=15003,
            )


# ── status ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_status_stopped_when_not_registered(
    service: InstanceLifecycleService,
) -> None:
    """status() returns STOPPED for non-registered instances."""
    status = await service.status("ghost")
    assert status == InstanceStatus.STOPPED


@pytest.mark.asyncio
async def test_status_stopped_when_no_pid_file(
    service: InstanceLifecycleService,
) -> None:
    """status() returns STOPPED for registered instances with no PID."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ws_root = Path(tmpdir) / "no-pid"
        await service.create(
            name="no-pid-instance",
            workspace_root=ws_root,
            web_port=18083,
            mlflow_port=15004,
        )
        status = await service.status("no-pid-instance")
        assert status == InstanceStatus.STOPPED


@pytest.mark.asyncio
async def test_status_unhealthy_when_pid_file_stale(
    service: InstanceLifecycleService,
) -> None:
    """status() returns UNHEALTHY when PID file exists but process dead."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ws_root = Path(tmpdir) / "stale-pid"
        await service.create(
            name="stale-pid-instance",
            workspace_root=ws_root,
            web_port=18084,
            mlflow_port=15005,
        )
        # Write a PID file with a non-existent PID.
        pid_path = ws_root / "logs" / "web.pid"
        pid_path.parent.mkdir(parents=True, exist_ok=True)
        pid_path.write_text("999999999")

        status = await service.status("stale-pid-instance")
        assert status == InstanceStatus.UNHEALTHY


# ── start ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_start_raises_for_missing_instance(
    service: InstanceLifecycleService,
) -> None:
    """start() raises ValueError for non-registered instances."""
    with pytest.raises(ValueError, match="not found"):
        await service.start("ghost")


@pytest.mark.asyncio
async def test_start_raises_when_port_in_use(
    service: InstanceLifecycleService,
) -> None:
    """start() raises RuntimeError when the web port is already bound."""
    import socket

    with tempfile.TemporaryDirectory() as tmpdir:
        ws_root = Path(tmpdir) / "port-busy"
        await service.create(
            name="port-busy",
            workspace_root=ws_root,
            web_port=18085,
            mlflow_port=15006,
        )

        # Bind the port to simulate another process using it.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", 18085))
            with pytest.raises(RuntimeError, match="already in use"):
                await service.start("port-busy")


# ── stop ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stop_raises_for_missing_instance(
    service: InstanceLifecycleService,
) -> None:
    """stop() raises ValueError for non-registered instances."""
    with pytest.raises(ValueError, match="not found"):
        await service.stop("ghost")


@pytest.mark.asyncio
async def test_stop_raises_when_no_pid_file(
    service: InstanceLifecycleService,
) -> None:
    """stop() raises FileNotFoundError when no PID file exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ws_root = Path(tmpdir) / "no-stop-pid"
        await service.create(
            name="no-stop-pid",
            workspace_root=ws_root,
            web_port=18086,
            mlflow_port=15007,
        )
        with pytest.raises(FileNotFoundError, match="No PID file"):
            await service.stop("no-stop-pid")


# ── get_registry ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_registry_returns_repo(
    service: InstanceLifecycleService,
) -> None:
    """get_registry() returns an InstanceRegistryRepository."""
    repo = await service.get_registry()
    assert isinstance(repo, InstanceRegistryRepository)


# ── Audit table DDL ──────────────────────────────────────────────────────

_AUDIT_EVENTS_DDL: str = """\
CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    sequence INTEGER NOT NULL,
    action_type VARCHAR(50) NOT NULL,
    target_type VARCHAR(50) NOT NULL,
    target_id VARCHAR(255),
    actor VARCHAR(100) NOT NULL,
    outcome VARCHAR(20) NOT NULL,
    reason TEXT,
    params_json TEXT,
    event_timestamp DATETIME NOT NULL,
    prev_hash VARCHAR(64) NOT NULL,
    entry_hash VARCHAR(64) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (sequence)
)
"""


@pytest_asyncio.fixture
async def audit_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh in-memory DB with instance_records AND
    audit_events tables.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.execute(text(_CREATE_TABLE_SQL))
        await conn.execute(text(_AUDIT_EVENTS_DDL))
        await conn.commit()

    factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with factory() as session:
        yield session

    await engine.dispose()


# ── list() ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_returns_empty_when_no_instances(
    service: InstanceLifecycleService,
) -> None:
    """list() returns empty list when no instances are registered."""
    result = await service.list()
    assert result == []


@pytest.mark.asyncio
async def test_list_returns_entries_with_live_status(
    service: InstanceLifecycleService,
) -> None:
    """list() returns each instance with a live-computed status."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ws1 = Path(tmpdir) / "a"
        ws2 = Path(tmpdir) / "b"
        await service.create(
            name="list-a",
            workspace_root=ws1,
            web_port=19001,
            mlflow_port=19002,
        )
        await service.create(
            name="list-b",
            workspace_root=ws2,
            web_port=19003,
            mlflow_port=19004,
        )

        result = await service.list()
        assert len(result) == 2

        names = [r["name"] for r in result]
        assert "list-a" in names
        assert "list-b" in names

        for entry in result:
            assert "name" in entry
            assert "workspace_root" in entry
            assert "web_port" in entry
            assert "mlflow_port" in entry
            assert "status" in entry
            # Both are stopped (no PID files).
            assert entry["status"] == "stopped"


@pytest.mark.asyncio
async def test_list_dict_shape(
    service: InstanceLifecycleService,
) -> None:
    """list() returns dicts matching the expected JSON-serialisable
    shape.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir) / "shape"
        await service.create(
            name="shape-test",
            workspace_root=ws,
            web_port=19005,
            mlflow_port=19006,
        )

        result = await service.list()
        assert len(result) == 1
        entry = result[0]
        assert isinstance(entry["name"], str)
        assert isinstance(entry["workspace_root"], str)
        assert isinstance(entry["web_port"], int)
        assert isinstance(entry["mlflow_port"], int)
        assert isinstance(entry["status"], str)
        assert entry["name"] == "shape-test"
        assert entry["status"] == "stopped"


# ── destroy() ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_destroy_raises_without_confirmation(
    service: InstanceLifecycleService,
) -> None:
    """destroy() raises ValueError when confirmed=False."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir) / "noconfirm"
        await service.create(
            name="no-confirm",
            workspace_root=ws,
            web_port=19007,
            mlflow_port=19008,
        )

        with pytest.raises(ValueError, match="confirmation"):
            await service.destroy("no-confirm", confirmed=False)


@pytest.mark.asyncio
async def test_destroy_removes_workspace_and_deregisters(
    service: InstanceLifecycleService,
    registry_session: AsyncSession,
) -> None:
    """destroy() with confirmed=True deletes workspace and removes from
    registry.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir) / "delete-me"
        await service.create(
            name="to-be-destroyed",
            workspace_root=ws,
            web_port=19009,
            mlflow_port=19010,
        )
        assert ws.exists()
        await registry_session.commit()

        await service.destroy("to-be-destroyed", confirmed=True)
        await registry_session.commit()

        # Workspace removed.
        assert not ws.exists()

        # Deregistered.
        repo = await service.get_registry()
        record = await repo.get_by_name("to-be-destroyed")
        assert record is None


@pytest.mark.asyncio
async def test_destroy_keep_data_preserves_workspace(
    service: InstanceLifecycleService,
    registry_session: AsyncSession,
) -> None:
    """destroy() with keep_data=True preserves the workspace on disk."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir) / "keep-data"
        await service.create(
            name="keep-data-instance",
            workspace_root=ws,
            web_port=19011,
            mlflow_port=19012,
        )
        assert ws.exists()
        await registry_session.commit()

        await service.destroy("keep-data-instance", keep_data=True, confirmed=True)
        await registry_session.commit()

        # Workspace preserved.
        assert ws.exists()
        assert (ws / "instance.json").exists()

        # But deregistered.
        repo = await service.get_registry()
        record = await repo.get_by_name("keep-data-instance")
        assert record is None


@pytest.mark.asyncio
async def test_destroy_force_stops_running_instance(
    service: InstanceLifecycleService,
    registry_session: AsyncSession,
) -> None:
    """destroy() with force=True stops a running instance before
    destroying.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir) / "force-stop"
        await service.create(
            name="force-destroy",
            workspace_root=ws,
            web_port=19013,
            mlflow_port=19014,
        )
        await registry_session.commit()

        # Simulate running: write a PID file and mock _process_exists
        # so status() reports RUNNING.
        pid_path = ws / "logs" / "web.pid"
        pid_path.parent.mkdir(parents=True, exist_ok=True)
        pid_path.write_text("99999")

        # Without force, destroy should refuse when instance is RUNNING.
        with patch(
            "anvil.services.instances.instance_lifecycle_service._process_exists",
            return_value=True,
        ):
            with pytest.raises(RuntimeError, match="running"):
                await service.destroy("force-destroy", confirmed=True)

        # With force, destroy should stop and destroy.
        # _process_exists: True for status() check, True for stop()
        # loop first check, False to break the stop loop.
        with (
            patch(
                "anvil.services.instances.instance_lifecycle_service._process_exists",
                side_effect=[True, True, False],
            ),
            patch("os.kill") as mock_kill,
        ):
            await service.destroy("force-destroy", force=True, confirmed=True)

        mock_kill.assert_called_once_with(99999, signal.SIGTERM)
        await registry_session.commit()

        assert not ws.exists()
        repo = await service.get_registry()
        record = await repo.get_by_name("force-destroy")
        assert record is None


# ── Audit assertions ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_emits_audit(audit_session: AsyncSession) -> None:
    """create() emits INSTANCE_CREATE when AuditService is wired."""
    from anvil.db.repositories.audit_events import AuditEventRepository
    from anvil.services.governance.audit_service import AuditService

    audit_repo = AuditEventRepository(audit_session)
    audit = AuditService(audit_repo)
    svc = InstanceLifecycleService(
        audit_session,
        registry_session=audit_session,
        audit=audit,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir) / "audit-create"
        await svc.create(
            name="audit-create-test",
            workspace_root=ws,
            web_port=19015,
            mlflow_port=19016,
        )

    events = await audit.list_events(action_type="instance_create")
    assert len(events) == 1
    assert events[0].target_id == "audit-create-test"
    assert events[0].action_type == "instance_create"
    assert events[0].target_type == "instance"


@pytest.mark.asyncio
async def test_destroy_emits_audit(audit_session: AsyncSession) -> None:
    """destroy() emits INSTANCE_DESTROY when AuditService is wired."""
    from anvil.db.repositories.audit_events import AuditEventRepository
    from anvil.services.governance.audit_service import AuditService

    audit_repo = AuditEventRepository(audit_session)
    audit = AuditService(audit_repo)
    svc = InstanceLifecycleService(
        audit_session,
        registry_session=audit_session,
        audit=audit,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir) / "audit-destroy"
        await svc.create(
            name="audit-destroy-test",
            workspace_root=ws,
            web_port=19017,
            mlflow_port=19018,
        )

    await svc.destroy("audit-destroy-test", keep_data=True, confirmed=True)

    events = await audit.list_events(action_type="instance_destroy")
    assert len(events) == 1
    assert events[0].target_id == "audit-destroy-test"
    assert events[0].action_type == "instance_destroy"


@pytest.mark.asyncio
async def test_start_stop_restart_emit_audit(audit_session: AsyncSession) -> None:
    """start(), stop(), restart() each emit their respective audit
    events when AuditService is wired.
    """
    from unittest.mock import patch

    from anvil.db.repositories.audit_events import AuditEventRepository
    from anvil.services.governance.audit_service import AuditService

    audit_repo = AuditEventRepository(audit_session)
    audit = AuditService(audit_repo)
    svc = InstanceLifecycleService(
        audit_session,
        registry_session=audit_session,
        audit=audit,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir) / "audit-cycle"
        await svc.create(
            name="audit-cycle-test",
            workspace_root=ws,
            web_port=19019,
            mlflow_port=19020,
        )

        # Mock start: Popen and port check.
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
            mock_proc.pid = 99999
            await svc.start("audit-cycle-test")

        # Mock stop: process exists check. os.kill is mocked to avoid
        # sending SIGTERM to any real process.
        with (
            patch(
                "anvil.services.instances.instance_lifecycle_service._process_exists",
                side_effect=[True, False],
            ),
            patch("os.kill"),
        ):
            await svc.stop("audit-cycle-test")

        # Check all three audit events.
        start_events = await audit.list_events(action_type="instance_start")
        assert len(start_events) == 1
        assert start_events[0].target_id == "audit-cycle-test"

        stop_events = await audit.list_events(action_type="instance_stop")
        assert len(stop_events) == 1
        assert stop_events[0].target_id == "audit-cycle-test"

        # Restart emits INSTANCE_RESTART.
        # Need a fresh PID file and port free for restart start phase.
        pid_path = ws / "logs" / "web.pid"
        pid_path.parent.mkdir(parents=True, exist_ok=True)
        pid_path.write_text("99999")

        with (
            patch(
                "anvil.services.instances.instance_lifecycle_service._is_port_free",
                return_value=True,
            ),
            patch(
                "anvil.services.instances.instance_lifecycle_service.subprocess.Popen"
            ) as mock_popen2,
            patch(
                "anvil.services.instances.instance_lifecycle_service._process_exists",
                return_value=False,
            ),
            patch("os.kill"),
        ):
            mock_proc2 = mock_popen2.return_value
            mock_proc2.pid = 99998
            await svc.restart("audit-cycle-test")

        restart_events = await audit.list_events(action_type="instance_restart")
        assert len(restart_events) == 1
        assert restart_events[0].target_id == "audit-cycle-test"
