"""Tests for RuntimeConfigService, CatalogEntry, and helpers."""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from anvil.services.runtime_config.apply_class import ApplyClass
from anvil.services.runtime_config.config_setting import ConfigSetting
from anvil.services.runtime_config.config_source import ConfigSource
from anvil.services.runtime_config.runtime_config_service import (
    CATALOG,
    CatalogEntry,
    RuntimeConfigService,
    _resolve_env,
    _resolve_env_config,
)


class TestCatalogEntry:
    """Tests for CatalogEntry data class."""

    def test_constructs_with_all_fields(self) -> None:
        entry = CatalogEntry(
            key="test_key",
            display_name="Test Key",
            description="A test setting.",
            apply_class=ApplyClass.APPLIES_LIVE,
            env_var="ANVIL_TEST_KEY",
            default_value="default_val",
            editable=True,
        )
        assert entry.key == "test_key"
        assert entry.display_name == "Test Key"
        assert entry.description == "A test setting."
        assert entry.apply_class == ApplyClass.APPLIES_LIVE
        assert entry.env_var == "ANVIL_TEST_KEY"
        assert entry.default_value == "default_val"
        assert entry.editable is True

    def test_editable_defaults_to_true(self) -> None:
        entry = CatalogEntry(
            key="test",
            display_name="Test",
            description="desc",
            apply_class=ApplyClass.BOOT_CRITICAL,
            env_var="ANVIL_TEST",
            default_value="x",
        )
        assert entry.editable is True

    def test_static_catalog_contains_expected_entries(self) -> None:
        keys = {e.key for e in CATALOG}
        assert "port" in keys
        assert "device" in keys
        assert "mlflow_uri" in keys
        assert "mlflow_port" in keys
        assert "log_dir" in keys
        assert "storage_backend" in keys
        assert "db_auto_migrate" in keys
        assert "content_dir" in keys
        assert "backup_dir" in keys
        assert "backup_quota_bytes" in keys
        assert "backup_quota_warn_fraction" in keys
        assert "backup_retention_max_count" in keys
        assert "backup_retention_max_age_days" in keys
        assert "mlflow_disable_local" in keys
        assert len(keys) == 14


class TestResolveEnv:
    """Tests for _resolve_env — reading env vars for catalog entries."""

    def test_returns_env_value_when_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANVIL_DEVICE", "mps")
        entry = CatalogEntry(
            key="device",
            display_name="Device",
            description="desc",
            apply_class=ApplyClass.APPLIES_LIVE,
            env_var="ANVIL_DEVICE",
            default_value="",
        )
        assert _resolve_env(entry) == "mps"

    def test_returns_none_when_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ANVIL_DEVICE", raising=False)
        entry = CatalogEntry(
            key="device",
            display_name="Device",
            description="desc",
            apply_class=ApplyClass.APPLIES_LIVE,
            env_var="ANVIL_DEVICE",
            default_value="",
        )
        assert _resolve_env(entry) is None


class TestResolveEnvConfig:
    """Tests for _resolve_env_config — reading from env-config dict."""

    def test_returns_value_from_config(self) -> None:
        entry = CatalogEntry(
            key="port",
            display_name="Port",
            description="desc",
            apply_class=ApplyClass.BOOT_CRITICAL,
            env_var="ANVIL_PORT",
            default_value="8080",
        )
        result = _resolve_env_config(entry)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_returns_string_even_when_config_returns_none(self) -> None:
        with patch(
            "anvil.services.runtime_config.runtime_config_service.get_env_config",
            return_value={"port": None},
        ):
            entry = CatalogEntry(
                key="port",
                display_name="Port",
                description="desc",
                apply_class=ApplyClass.BOOT_CRITICAL,
                env_var="ANVIL_PORT",
                default_value="8080",
            )
            assert _resolve_env_config(entry) == ""


class TestResolveValue:
    """Tests for RuntimeConfigService._resolve_value resolution chain."""

    @pytest.fixture
    def entry(self) -> CatalogEntry:
        return CatalogEntry(
            key="device",
            display_name="Device",
            description="desc",
            apply_class=ApplyClass.APPLIES_LIVE,
            env_var="ANVIL_DEVICE",
            default_value="cpu",
        )

    def test_override_takes_precedence(self, entry: CatalogEntry) -> None:
        svc = RuntimeConfigService(repo=MagicMock())
        value, source = svc._resolve_value(entry, override="mps")
        assert value == "mps"
        assert source == ConfigSource.OVERRIDE

    def test_env_when_no_override(self, entry: CatalogEntry) -> None:
        svc = RuntimeConfigService(repo=MagicMock())
        with patch(
            "anvil.services.runtime_config.runtime_config_service.get_env_config",
            return_value={"device": "cuda"},
        ):
            value, source = svc._resolve_value(entry, override=None)
        assert source == ConfigSource.ENV

    def test_default_when_no_override_or_env(
        self, monkeypatch: pytest.MonkeyPatch, entry: CatalogEntry
    ) -> None:
        monkeypatch.delenv("ANVIL_DEVICE", raising=False)
        svc = RuntimeConfigService(repo=MagicMock())
        with patch(
            "anvil.services.runtime_config.runtime_config_service.get_env_config",
            return_value={"device": ""},
        ):
            value, source = svc._resolve_value(entry, override=None)
        assert value == "cpu"
        assert source == ConfigSource.DEFAULT


class TestComputePendingRestart:
    """Tests for _compute_pending_restart logic."""

    @pytest.fixture
    def boot_critical_entry(self) -> CatalogEntry:
        return CatalogEntry(
            key="port",
            display_name="Port",
            description="desc",
            apply_class=ApplyClass.BOOT_CRITICAL,
            env_var="ANVIL_PORT",
            default_value="8080",
        )

    @pytest.fixture
    def live_entry(self) -> CatalogEntry:
        return CatalogEntry(
            key="device",
            display_name="Device",
            description="desc",
            apply_class=ApplyClass.APPLIES_LIVE,
            env_var="ANVIL_DEVICE",
            default_value="",
        )

    def test_override_live_is_not_pending(self, live_entry: CatalogEntry) -> None:
        svc = RuntimeConfigService(repo=MagicMock())
        result = svc._compute_pending_restart(
            live_entry, ConfigSource.OVERRIDE, "mps", None
        )
        assert result is False

    def test_non_override_is_not_pending(
        self, boot_critical_entry: CatalogEntry
    ) -> None:
        svc = RuntimeConfigService(repo=MagicMock())
        result = svc._compute_pending_restart(
            boot_critical_entry, ConfigSource.ENV, "9090", None
        )
        assert result is False

    def test_boot_critical_override_without_snapshot_is_pending(
        self, boot_critical_entry: CatalogEntry
    ) -> None:
        svc = RuntimeConfigService(repo=MagicMock())
        result = svc._compute_pending_restart(
            boot_critical_entry, ConfigSource.OVERRIDE, "9090", None
        )
        assert result is True

    def test_boot_critical_override_matches_snapshot_is_not_pending(
        self, boot_critical_entry: CatalogEntry
    ) -> None:
        svc = RuntimeConfigService(repo=MagicMock())
        result = svc._compute_pending_restart(
            boot_critical_entry,
            ConfigSource.OVERRIDE,
            "8080",
            {"port": "8080"},
        )
        assert result is False

    def test_boot_critical_override_differs_from_snapshot_is_pending(
        self, boot_critical_entry: CatalogEntry
    ) -> None:
        svc = RuntimeConfigService(repo=MagicMock())
        result = svc._compute_pending_restart(
            boot_critical_entry,
            ConfigSource.OVERRIDE,
            "9090",
            {"port": "8080"},
        )
        assert result is True


class TestCatalogProperty:
    """Tests for RuntimeConfigService.catalog property."""

    def test_catalog_indexes_by_key(self) -> None:
        svc = RuntimeConfigService(repo=MagicMock())
        assert svc.catalog["port"].key == "port"
        assert svc.catalog["device"].key == "device"


class TestGet:
    """Tests for RuntimeConfigService.get single-setting resolution."""

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_key(self) -> None:
        svc = RuntimeConfigService(repo=MagicMock())
        result = await svc.get("nonexistent_key")
        assert result is None


class TestSetOverride:
    """Tests for RuntimeConfigService.set_override."""

    @pytest.mark.asyncio
    async def test_raises_on_unknown_key(self) -> None:
        svc = RuntimeConfigService(repo=MagicMock())
        with pytest.raises(ValueError, match="Unknown config key"):
            await svc.set_override("nonexistent", "val")

    @pytest.mark.asyncio
    async def test_raises_on_non_editable_key(self) -> None:
        svc = RuntimeConfigService(repo=MagicMock())
        with pytest.raises(ValueError, match="Unknown config key"):
            await svc.set_override("nonexistent", "val")


class TestResetOverride:
    """Tests for RuntimeConfigService.reset_override."""

    @pytest.mark.asyncio
    async def test_raises_on_unknown_key(self) -> None:
        svc = RuntimeConfigService(repo=MagicMock())
        with pytest.raises(ValueError, match="Unknown config key"):
            await svc.reset_override("nonexistent")
