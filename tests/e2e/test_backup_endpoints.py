# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""E2E tests for backup & restore API endpoints (feature 026).

Tests assume the ``client`` fixture (from ``tests/conftest.py``) is
available.  The BackupService is set up on ``app.state`` manually
because the app lifespan does not run in test mode.
"""

import tempfile
from pathlib import Path

import pytest

from anvil.api.app import app


@pytest.fixture(autouse=True)
def _setup_backup_service():
    """Ensure ``app.state.backup_service`` is available for each test."""
    from anvil.services.backup.backup_service import BackupService

    tmp = tempfile.mkdtemp()
    svc = BackupService(backup_dir=tmp, quota_bytes=10 * 1024**3)
    app.state.backup_service = svc
    yield
    import shutil

    shutil.rmtree(tmp, ignore_errors=True)


BACKUP_ID = "00000000T000000Z-e2etest"


@pytest.mark.asyncio
async def test_create_backup_returns_202(client):
    r = await client.post("/v1/backup")
    assert r.status_code == 202
    data = r.json()
    assert "backup_id" in data
    assert data["status"] == "creating"


@pytest.mark.asyncio
async def test_list_backups(client):
    await client.post("/v1/backup")
    r = await client.get("/v1/backup")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_get_backup_not_found(client):
    r = await client.get("/v1/backup/nonexistent")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_backup_status(client):
    r = await client.get("/v1/backup/status")
    assert r.status_code == 200
    data = r.json()
    assert "backup_count" in data
    assert "total_bytes" in data


@pytest.mark.asyncio
async def test_create_then_verify(client):
    """Create a backup, then verify it (FR-025)."""
    create_r = await client.post("/v1/backup")
    assert create_r.status_code == 202
    bid = create_r.json()["backup_id"]

    # Verify: should succeed since the archive was created.
    vr = await client.post(f"/v1/backup/{bid}/verify")
    assert vr.status_code == 200
    vdata = vr.json()
    assert "valid" in vdata


@pytest.mark.asyncio
async def test_delete_backup(client):
    """Create two backups, then delete the first (need >1 to avoid last-backup guard)."""
    r1 = await client.post("/v1/backup")
    assert r1.status_code == 202
    bid1 = r1.json()["backup_id"]

    r2 = await client.post("/v1/backup")
    assert r2.status_code == 202
    bid2 = r2.json()["backup_id"]

    # Delete the first backup.
    dr = await client.delete(f"/v1/backup/{bid1}")
    assert dr.status_code == 200
    data = dr.json()
    assert data["deleted"] == bid1


@pytest.mark.asyncio
async def test_delete_nonexistent_backup(client):
    dr = await client.delete("/v1/backup/nonexistent")
    assert dr.status_code == 404


@pytest.mark.asyncio
async def test_restore_requires_confirm(client):
    """Restore without a confirm token returns 400 (FR-021)."""
    create_r = await client.post("/v1/backup")
    assert create_r.status_code == 202
    bid = create_r.json()["backup_id"]

    rr = await client.post(f"/v1/backup/{bid}/restore", json={"confirm": ""})
    assert rr.status_code == 400


@pytest.mark.asyncio
async def test_restore_happy_path(client):
    """Restore with correct token returns 202 (FR-018, FR-021)."""
    create_r = await client.post("/v1/backup")
    assert create_r.status_code == 202
    bid = create_r.json()["backup_id"]

    rr = await client.post(f"/v1/backup/{bid}/restore", json={"confirm": "RESTORE"})
    assert rr.status_code == 202
    data = rr.json()
    assert "safety_snapshot_id" in data
    assert data["status"] == "completed"


@pytest.mark.asyncio
async def test_cleanup_safety(client):
    """Cleanup-safety removes safety snapshots but leaves real backups intact."""
    # Create a real backup.
    r1 = await client.post("/v1/backup")
    assert r1.status_code == 202

    # Run restore, which auto-creates a safety snapshot.
    lst = await client.get("/v1/backup")
    bids = [b["backup_id"] for b in lst.json()]
    assert len(bids) >= 1
    rr = await client.post(f"/v1/backup/{bids[0]}/restore", json={"confirm": "RESTORE"})
    assert rr.status_code == 202, f"restore failed: {rr.text}"
    data = rr.json()
    safety_id = data["safety_snapshot_id"]

    # Now cleanup safety snapshots.
    cr = await client.post("/v1/backup/cleanup-safety")
    assert cr.status_code == 200, f"cleanup failed: {cr.text}"
    cdata = cr.json()
    assert cdata["deleted_count"] >= 1, f"expected >=1 safety snapshots, got {cdata}"

    # Verify safety snapshot is gone but backup remains.
    lst2 = await client.get("/v1/backup")
    remaining = [b["backup_id"] for b in lst2.json()]
    assert safety_id not in remaining
    assert bids[0] in remaining
