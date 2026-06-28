# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Instance lifecycle management — create, start, stop, status, list, destroy.

Provides :class:`InstanceLifecycleService` for operating on isolated
anvil instances.  Each instance gets its own workspace directory
(containing per-instance data, logs, and an ``instance.json`` boot
file) and a row in the global host-level registry (for cross-instance
collision detection).

The service is the single entry point for the instance lifecycle —
all CLI and (future) API actions delegate here.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from ...db.models.instance_record import InstanceRecord
from ...db.repositories.instance_registry import (
    InstanceRegistryRepository,
    create_registry_session,
)
from ...workspace.boot_config import BootConfig
from ..governance.audit_action import AuditAction
from ..governance.audit_outcome import AuditOutcome
from ..governance.audit_service import AuditService
from ..governance.audit_target_type import AuditTargetType
from .instance_status import InstanceStatus
from .workspace_lock import WorkspaceLock

logger = logging.getLogger(__name__)

# Regex for valid instance names: alphanumeric, underscore, hyphen.
_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")

# Base port for auto-allocation (start probing here).
_BASE_WEB_PORT: int = 8080
_BASE_MLFLOW_PORT: int = 5001
_PORT_PROBE_MAX_ATTEMPTS: int = 100


def _find_free_port(base: int = 0) -> int:
    """Probe for an available TCP port on localhost.

    Uses ``socket.socket().bind(('localhost', 0))`` when *base* is 0
    (let the OS pick), or scans upward from *base*.

    Parameters
    ----------
    base : int
        Starting port to probe, or 0 for OS-assigned.

    Returns
    -------
    int
        A free port number.
    """
    if base == 0:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", 0))
            return int(s.getsockname()[1])
    for port in range(base, base + _PORT_PROBE_MAX_ATTEMPTS):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("localhost", port))
                return port
            except OSError:
                continue
    raise RuntimeError(
        f"Could not find a free port starting from {base} "
        f"(tried {_PORT_PROBE_MAX_ATTEMPTS} ports)"
    )


def _is_port_free(port: int) -> bool:
    """Check whether a TCP port is available on localhost.

    Parameters
    ----------
    port : int
        Port number to check.

    Returns
    -------
    bool
        ``True`` if the port is free.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("localhost", port))
            return True
        except OSError:
            return False


class InstanceLifecycleService:
    """Creates, starts, stops, lists, destroys, and monitors isolated
    anvil instances.

    Parameters
    ----------
    session : AsyncSession
        The per-instance app DB session (for future migration/init
        operations).  The service also manages its own registry
        session for the global registry.
    registry_session : AsyncSession, optional
        Session bound to the global registry DB.  If omitted, one is
        created lazily via :func:`create_registry_session`.
    audit : AuditService, optional
        The hash-chained audit trail service.  When provided, every
        lifecycle action emits an audit event.
    """

    def __init__(
        self,
        session: AsyncSession,
        registry_session: AsyncSession | None = None,
        audit: AuditService | None = None,
    ) -> None:
        self._session = session
        self._registry_session: AsyncSession | None = registry_session
        self._audit = audit

    async def _get_registry_session(self) -> AsyncSession:
        """Return the registry session, creating it lazily if needed."""
        if self._registry_session is None:
            self._registry_session = await create_registry_session()
        return self._registry_session

    async def get_registry(self) -> InstanceRegistryRepository:
        """Return an ``InstanceRegistryRepository`` bound to the global
        registry session.

        Returns
        -------
        InstanceRegistryRepository
        """
        session = await self._get_registry_session()
        return InstanceRegistryRepository(session)

    async def _emit_audit(
        self,
        action: AuditAction,
        target_id: str,
        outcome: AuditOutcome = AuditOutcome.SUCCESS,
    ) -> None:
        """Emit an instance lifecycle audit event if the audit service
        is configured.

        Parameters
        ----------
        action : AuditAction
            The action type (e.g. ``INSTANCE_CREATE``).
        target_id : str
            Instance name.
        outcome : AuditOutcome
            Outcome of the action (default SUCCESS).
        """
        if self._audit is not None:
            await self._audit.record(
                action_type=action.value,
                target_type=AuditTargetType.INSTANCE.value,
                target_id=target_id,
                actor="system",
                outcome=outcome.value,
            )

    # ── CREATE ───────────────────────────────────────────────────────────

    async def create(
        self,
        name: str,
        workspace_root: Path,
        *,
        web_port: int | None = None,
        mlflow_port: int | None = None,
    ) -> InstanceRecord:
        """Create a new isolated instance.

        Steps:
        1. Validate the instance name.
        2. Check for workspace overlap with existing instances.
        3. Auto-allocate free ports if not pinned.
        4. Check for port conflicts with existing instances.
        5. Reclaim stale workspace lock if present.
        6. Create the workspace directory tree.
        7. Write the boot config (``instance.json``).
        8. Register in the global registry.

        Parameters
        ----------
        name : str
            Instance identifier.  Must match ``^[a-zA-Z0-9_-]+$``.
        workspace_root : Path
            Absolute path to the workspace root (created if missing).
        web_port : int, optional
            Web/uvicorn port.  Auto-allocated if omitted.
        mlflow_port : int, optional
            MLflow sidecar port.  Auto-allocated if omitted.

        Returns
        -------
        InstanceRecord
            The newly registered instance record.

        Raises
        ------
        ValueError
            If the name is invalid or a collision is detected.
        """
        # 1. Validate name.
        if not _NAME_PATTERN.match(name):
            raise ValueError(
                f"Invalid instance name '{name}': must match " f"^[a-zA-Z0-9_-]+$"
            )

        workspace_root = workspace_root.resolve()
        registry = await self.get_registry()

        # 2. Check workspace overlap.
        overlap = await registry.find_workspace_overlap(str(workspace_root))
        if overlap is not None:
            raise ValueError(
                f"Workspace {workspace_root} overlaps with "
                f"{overlap.workspace_root} (owned by "
                f"'{overlap.name}')"
            )

        # 3. Auto-allocate ports.
        resolved_web_port = web_port or _find_free_port(_BASE_WEB_PORT)
        resolved_mlflow_port = mlflow_port or _find_free_port(_BASE_MLFLOW_PORT)

        # 4. Check port conflicts against existing instances.
        port_conflict = await registry.find_port_conflict(
            resolved_web_port, resolved_mlflow_port
        )
        if port_conflict is not None:
            if port_conflict.web_port == resolved_web_port:
                raise ValueError(
                    f"Port {resolved_web_port} is already in use by "
                    f"instance '{port_conflict.name}'"
                )
            raise ValueError(
                f"Port {resolved_mlflow_port} is already in use by "
                f"instance '{port_conflict.name}'"
            )

        # 5. Reclaim stale workspace lock if present.
        await WorkspaceLock.reclaim(workspace_root)

        # 6. Create workspace directory tree.
        workspace_root.mkdir(parents=True, exist_ok=True)
        (workspace_root / "data").mkdir(exist_ok=True)
        (workspace_root / "logs").mkdir(exist_ok=True)
        (workspace_root / "mlruns").mkdir(exist_ok=True)

        # 7. Write boot config.
        state_db_path = str(workspace_root / "data" / "anvil-state.db")
        boot = BootConfig(
            name=name,
            workspace_root=str(workspace_root),
            web_port=resolved_web_port,
            mlflow_port=resolved_mlflow_port,
            state_db_path=state_db_path,
        )
        boot.write(workspace_root / "instance.json")

        # 8. Register in global registry.
        record = InstanceRecord(
            name=name,
            workspace_root=str(workspace_root),
            web_port=resolved_web_port,
            mlflow_port=resolved_mlflow_port,
        )
        result = await registry.register(record)
        await self._emit_audit(AuditAction.INSTANCE_CREATE, name)
        return result

    # ── START ────────────────────────────────────────────────────────────

    async def start(self, name: str) -> None:
        """Start an isolated instance's web process.

        1. Look up the instance in the global registry.
        2. Acquire the workspace lock (fail if held by live process).
        3. Verify ports are not in use by another process.
        4. Spawn ``uvicorn`` as a subprocess with instance-specific
           environment variables.
        5. Write a PID file to ``{workspace}/logs/web.pid``.

        Parameters
        ----------
        name : str
            Instance name to start.

        Raises
        ------
        ValueError
            If the instance is not registered.
        RuntimeError
            If the instance is already running, or workspace lock is
            held by a live process.
        """
        registry = await self.get_registry()
        record = await registry.get_by_name(name)
        if record is None:
            raise ValueError(f"Instance '{name}' not found in the global registry")

        workspace_root = Path(record.workspace_root)
        pid_path = workspace_root / "logs" / "web.pid"

        # Acquire workspace lock.
        lock = WorkspaceLock(workspace_root)
        if not await lock.acquire():
            lock_pid = int((lock.lock_path).read_text().strip())
            raise RuntimeError(
                f"Instance '{name}' cannot start: workspace lock is "
                f"held by live process (PID {lock_pid})"
            )

        # Check if already running.
        if pid_path.exists():
            existing_pid = int(pid_path.read_text().strip())
            if _process_exists(existing_pid):
                raise RuntimeError(
                    f"Instance '{name}' is already running (PID " f"{existing_pid})"
                )
            # Stale PID file — clean it.
            pid_path.unlink(missing_ok=True)

        # Verify ports are free (FR-019).
        if not _is_port_free(record.web_port):
            raise RuntimeError(
                f"Web port {record.web_port} is already in use by " f"another process"
            )

        # Build environment for the child process.
        env = os.environ.copy()
        env["ANVIL_WORKSPACE_DIR"] = str(workspace_root)
        env["ANVIL_PORT"] = str(record.web_port)
        env["ANVIL_STATE_DB_PATH"] = str(workspace_root / "data" / "anvil-state.db")
        env["ANVIL_MLFLOW_URI"] = f"http://127.0.0.1:{record.mlflow_port}"

        # Spawn uvicorn subprocess.
        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "anvil.api.app:app",
            "--host",
            "0.0.0.0",
            "--port",
            str(record.web_port),
        ]
        proc = subprocess.Popen(
            cmd,
            start_new_session=True,
            cwd=str(workspace_root),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Write PID file.
        pid_path.parent.mkdir(parents=True, exist_ok=True)
        pid_path.write_text(str(proc.pid))
        logger.info(
            "Started instance '%s' on port %d (PID %d)",
            name,
            record.web_port,
            proc.pid,
        )
        await self._emit_audit(AuditAction.INSTANCE_START, name)

    # ── STOP ─────────────────────────────────────────────────────────────

    async def stop(self, name: str) -> None:
        """Stop an isolated instance's web process.

        1. Read the PID file.
        2. Send ``SIGTERM`` and wait up to 10 seconds.
        3. Send ``SIGKILL`` if the process is still alive.
        4. Clean up the PID file.
        5. Release the workspace lock.

        Parameters
        ----------
        name : str
            Instance name to stop.

        Raises
        ------
        ValueError
            If the instance is not registered.
        FileNotFoundError
            If no PID file exists for the instance.
        """
        registry = await self.get_registry()
        record = await registry.get_by_name(name)
        if record is None:
            raise ValueError(f"Instance '{name}' not found in the global registry")

        pid_path = Path(record.workspace_root) / "logs" / "web.pid"
        if not pid_path.exists():
            raise FileNotFoundError(
                f"No PID file found for instance '{name}' at {pid_path}"
            )

        pid = int(pid_path.read_text().strip())
        try:
            os.kill(pid, signal.SIGTERM)
            # Wait up to 10 seconds for graceful shutdown.
            for _ in range(100):
                if not _process_exists(pid):
                    break
                await asyncio_sleep(0.1)
            else:
                # Process still alive — force kill.
                os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass  # Already dead.

        pid_path.unlink(missing_ok=True)

        # Release workspace lock.
        workspace_root = Path(record.workspace_root)
        lock = WorkspaceLock(workspace_root)
        await lock.release()

        logger.info("Stopped instance '%s' (PID %d)", name, pid)
        await self._emit_audit(AuditAction.INSTANCE_STOP, name)

    # ── RESTART ──────────────────────────────────────────────────────────

    async def restart(self, name: str) -> None:
        """Restart an isolated instance (stop then start).

        1. Stop the instance (graceful SIGTERM + SIGKILL fallback).
        2. Start the instance (spawn uvicorn subprocess).

        Parameters
        ----------
        name : str
            Instance name to restart.

        Raises
        ------
        ValueError
            If the instance is not registered.
        FileNotFoundError
            If the instance has no PID file.
        RuntimeError
            If the instance's ports are still occupied after stop.
        """
        await self.stop(name)
        await self.start(name)
        await self._emit_audit(AuditAction.INSTANCE_RESTART, name)

    # ── STATUS ───────────────────────────────────────────────────────────

    async def status(self, name: str) -> InstanceStatus:
        """Return the live runtime status of an instance.

        The status is recomputed from the PID file and process table
        — never read from a stored field.

        Parameters
        ----------
        name : str
            Instance name to query.

        Returns
        -------
        InstanceStatus
            ``running``, ``stopped``, or ``unhealthy``.
        """
        registry = await self.get_registry()
        record = await registry.get_by_name(name)
        if record is None:
            return InstanceStatus(InstanceStatus.STOPPED)

        pid_path = Path(record.workspace_root) / "logs" / "web.pid"
        if not pid_path.exists():
            return InstanceStatus(InstanceStatus.STOPPED)

        pid = int(pid_path.read_text().strip())
        if _process_exists(pid):
            return InstanceStatus(InstanceStatus.RUNNING)

        # PID file exists but process is dead → unhealthy.
        return InstanceStatus(InstanceStatus.UNHEALTHY)

    # ── LIST ──────────────────────────────────────────────────────────────

    async def list(self) -> list[dict[str, object]]:
        """List all registered instances with their live status.

        Fetches all records from the global registry and probes each
        one's runtime status (from PID file + process table).

        Returns
        -------
        list[dict]
            Each dict has keys ``name``, ``workspace_root``,
            ``web_port``, ``mlflow_port``, ``status``.
        """
        registry = await self.get_registry()
        records = await registry.list_all()
        result: list[dict[str, object]] = []
        for rec in records:
            status = await self.status(rec.name)
            result.append(
                {
                    "name": rec.name,
                    "workspace_root": rec.workspace_root,
                    "web_port": rec.web_port,
                    "mlflow_port": rec.mlflow_port,
                    "status": status.value,
                }
            )
        return result

    # ── DESTROY ───────────────────────────────────────────────────────────

    async def destroy(
        self,
        name: str,
        *,
        keep_data: bool = False,
        force: bool = False,
        confirmed: bool = False,
    ) -> None:
        """Destroy a registered instance.

        Steps:
        1. Verify the instance exists.
        2. If running: stop (``--force``) or reject.
        3. Require explicit confirmation (``confirmed=True``).
        4. Deregister from the global registry.
        5. Delete the workspace tree unless ``keep_data``.
        6. Emit audit.

        Parameters
        ----------
        name : str
            Instance name to destroy.
        keep_data : bool
            Preserve workspace data on disk if ``True``.
        force : bool
            Stop a running instance before destroying if ``True``.
        confirmed : bool
            Must be ``True`` to proceed (safety gate).

        Raises
        ------
        ValueError
            If the instance is not registered or confirmation is
            missing.
        RuntimeError
            If the instance is running and ``force`` is ``False``.
        """
        if not confirmed:
            raise ValueError(f"Destroy requires confirmation for instance '{name}'")

        registry = await self.get_registry()
        record = await registry.get_by_name(name)
        if record is None:
            raise ValueError(f"Instance '{name}' not found in the global registry")

        # If running: stop if force, otherwise reject.
        current_status = await self.status(name)
        if current_status == InstanceStatus.RUNNING:
            if force:
                await self.stop(name)
            else:
                raise RuntimeError(
                    f"Instance '{name}' is running. Use force=True to "
                    f"stop before destroying."
                )

        await registry.deregister(name)
        if not keep_data:
            workspace_root = Path(record.workspace_root)
            if workspace_root.exists():
                shutil.rmtree(workspace_root)

        await self._emit_audit(AuditAction.INSTANCE_DESTROY, name)


# ── Internal helpers ─────────────────────────────────────────────────────


def _process_exists(pid: int) -> bool:
    """Check whether a process with the given PID is alive.

    Parameters
    ----------
    pid : int
        Process ID to check.

    Returns
    -------
    bool
        ``True`` if the process exists.
    """
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


async def asyncio_sleep(seconds: float) -> None:
    """Async-compatible sleep (avoids top-level ``import asyncio``)."""
    await asyncio.sleep(seconds)
