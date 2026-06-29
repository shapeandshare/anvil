"""Tests for governance API endpoints.

Covers /v1/governance/* and /v1/datasets/*/takedown routes.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from anvil.api.app import app
from anvil.api.deps import get_workbench


@pytest.fixture
def mock_workbench():
    wb = MagicMock()
    wb.audit = MagicMock()
    wb.governance = MagicMock()
    wb.dataset_repo = MagicMock()
    return wb


@pytest.fixture
def override_dep(mock_workbench):
    app.dependency_overrides[get_workbench] = lambda: mock_workbench
    yield
    app.dependency_overrides.clear()


class TestListAuditEvents:
    async def test_returns_events(self, client, mock_workbench, override_dep):
        mock_event = MagicMock()
        mock_event.id = 1
        mock_event.sequence = 1
        mock_event.action_type = "upload"
        mock_event.target_type = "dataset"
        mock_event.target_id = "42"
        mock_event.actor = "user"
        mock_event.outcome = "success"
        mock_event.reason = None
        mock_event.event_timestamp = "2026-06-01T00:00:00"
        mock_workbench.audit.list_events = AsyncMock(return_value=[mock_event])

        resp = await client.get("/v1/governance/audit")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 1
        assert data["data"][0]["action_type"] == "upload"

    async def test_events_with_filters(self, client, mock_workbench, override_dep):
        mock_workbench.audit.list_events = AsyncMock(return_value=[])
        resp = await client.get("/v1/governance/audit?target_type=dataset&limit=10")
        assert resp.status_code == 200


class TestVerifyAuditChain:
    async def test_chain_valid(self, client, mock_workbench, override_dep):
        from anvil.services.governance.chain_verify_result import ChainVerifyResult

        mock_workbench.audit.verify_chain = AsyncMock(
            return_value=ChainVerifyResult(
                valid=True, break_at_sequence=None, entries_checked=5
            )
        )
        resp = await client.get("/v1/governance/audit/verify")
        assert resp.status_code == 200
        assert resp.json()["data"]["valid"] is True


class TestDatasetGovernanceReport:
    async def test_report_success(self, client, mock_workbench, override_dep):
        mock_dataset = MagicMock()
        mock_dataset.id = 1
        mock_workbench.dataset_repo.get = AsyncMock(return_value=mock_dataset)

        mock_prov = MagicMock()
        mock_prov.source_description = "test"
        mock_prov.license = "MIT"
        mock_prov.attribution = "author"
        mock_prov.origin = MagicMock()
        mock_prov.origin.value = "user"
        mock_workbench.governance.get_provenance = AsyncMock(return_value=mock_prov)
        mock_workbench.audit.list_events = AsyncMock(return_value=[])

        resp = await client.get("/v1/governance/datasets/1/report")
        assert resp.status_code == 200
        assert resp.json()["error"] is None

    async def test_report_not_found(self, client, mock_workbench, override_dep):
        mock_workbench.dataset_repo.get = AsyncMock(return_value=None)
        resp = await client.get("/v1/governance/datasets/999/report")
        assert resp.status_code == 404


class TestListLicenses:
    async def test_returns_licenses(self, client, mock_workbench, override_dep):
        lic = MagicMock()
        lic.id = 1
        lic.identifier = "MIT"
        lic.display_name = "MIT License"
        lic.requires_attribution = False
        lic.redistribution_allowed = True
        lic.is_own_content_sentinel = False
        mock_workbench.governance.list_licenses = AsyncMock(return_value=[lic])

        resp = await client.get("/v1/governance/licenses")
        assert resp.status_code == 200
        assert resp.json()["data"][0]["identifier"] == "MIT"


class TestTakedown:
    async def test_takedown_success(self, client, mock_workbench, override_dep):
        mock_dataset = MagicMock()
        mock_dataset.name = "test-ds"
        mock_workbench.dataset_repo.get = AsyncMock(return_value=mock_dataset)
        mock_workbench.audit.record = AsyncMock()

        resp = await client.post(
            "/v1/datasets/1/takedown",
            json={"reason": "Copyright violation"},
        )
        assert resp.status_code == 200

    async def test_takedown_not_found(self, client, mock_workbench, override_dep):
        mock_workbench.dataset_repo.get = AsyncMock(return_value=None)
        resp = await client.post(
            "/v1/datasets/999/takedown",
            json={"reason": "test"},
        )
        assert resp.status_code == 404
