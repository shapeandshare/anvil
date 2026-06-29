"""Tests for runtime config API endpoints.

Covers GET/PUT /v1/config/* routes against a mocked workbench.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from anvil.api.app import app
from anvil.api.deps import get_workbench
from anvil.services._shared.asset_state import AssetState
from anvil.services.runtime_config.apply_class import ApplyClass
from anvil.services.runtime_config.config_setting import ConfigSetting
from anvil.services.runtime_config.config_source import ConfigSource


@pytest.fixture
def mock_workbench():
    wb = MagicMock()
    wb.runtime_config = MagicMock()
    wb.audit = MagicMock()
    wb.audit.record = AsyncMock()
    return wb


@pytest.fixture
def sample_setting():
    return ConfigSetting(
        key="app.max_workers",
        value="4",
        source=ConfigSource.ENV,
        apply_class=ApplyClass.APPLIES_LIVE,
        editable=True,
        display_name="Max Workers",
        description="Max parallel workers",
        env_var="APP_MAX_WORKERS",
        default_value="2",
    )


@pytest.fixture
def override_dep(mock_workbench):
    app.dependency_overrides[get_workbench] = lambda: mock_workbench
    yield
    app.dependency_overrides.clear()


class TestListConfig:
    async def test_returns_all_settings(self, client, mock_workbench, sample_setting, override_dep):
        mock_workbench.runtime_config.get_all = AsyncMock(return_value=[sample_setting])
        resp = await client.get("/v1/config")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["key"] == "app.max_workers"
        assert data[0]["value"] == "4"

    async def test_empty_config(self, client, mock_workbench, override_dep):
        mock_workbench.runtime_config.get_all = AsyncMock(return_value=[])
        resp = await client.get("/v1/config")
        assert resp.status_code == 200
        assert resp.json() == []


class TestGetConfig:
    async def test_get_existing(self, client, mock_workbench, sample_setting, override_dep):
        mock_workbench.runtime_config.get = AsyncMock(return_value=sample_setting)
        resp = await client.get("/v1/config/app.max_workers")
        assert resp.status_code == 200
        assert resp.json()["key"] == "app.max_workers"

    async def test_get_missing(self, client, mock_workbench, override_dep):
        mock_workbench.runtime_config.get = AsyncMock(return_value=None)
        resp = await client.get("/v1/config/nonexistent")
        assert resp.status_code == 404


class TestUpdateConfig:
    async def test_update_success(self, client, mock_workbench, sample_setting, override_dep):
        mock_workbench.runtime_config.set_override = AsyncMock(return_value=sample_setting)
        mock_workbench.audit.record = AsyncMock()
        resp = await client.put("/v1/config/app.max_workers", json={"value": "8"})
        assert resp.status_code == 200
        assert resp.json()["value"] == "4"

    async def test_update_not_editable(self, client, mock_workbench, override_dep):
        mock_workbench.runtime_config.set_override = AsyncMock(
            side_effect=ValueError("not editable")
        )
        resp = await client.put("/v1/config/app.max_workers", json={"value": "8"})
        assert resp.status_code == 400

    async def test_update_unknown(self, client, mock_workbench, override_dep):
        mock_workbench.runtime_config.set_override = AsyncMock(
            side_effect=ValueError("Unknown config key")
        )
        resp = await client.put("/v1/config/unknown", json={"value": "x"})
        assert resp.status_code == 400


class TestResetConfig:
    async def test_reset_success(self, client, mock_workbench, sample_setting, override_dep):
        mock_workbench.runtime_config.reset_override = AsyncMock(return_value=sample_setting)
        mock_workbench.audit.record = AsyncMock()
        resp = await client.post("/v1/config/app.max_workers/reset")
        assert resp.status_code == 200
        assert resp.json()["key"] == "app.max_workers"

    async def test_reset_unknown(self, client, mock_workbench, override_dep):
        mock_workbench.runtime_config.reset_override = AsyncMock(
            side_effect=ValueError("Unknown config key")
        )
        resp = await client.post("/v1/config/unknown/reset")
        assert resp.status_code == 400
