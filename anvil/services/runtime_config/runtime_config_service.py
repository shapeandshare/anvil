# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Runtime config resolution service.

Resolves config values through a three-layer chain:
persisted override > environment variable > code-level default.
Provides the static setting catalog enumerating every configurable
key with its apply_class and editable flag.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from ...config import get_config as get_env_config
from .apply_class import ApplyClass
from .config_setting import ConfigSetting
from .config_source import ConfigSource

if TYPE_CHECKING:
    from ...db.repositories.runtime_config import RuntimeConfigRepository


class CatalogEntry:
    """A single entry in the static setting catalog.

    Parameters
    ----------
    key : str
        The setting name (e.g. ``device``, ``mlflow_uri``).
    display_name : str
        Human-readable label for the UI.
    description : str
        Brief description of what this setting controls.
    apply_class : ApplyClass
        How changes take effect.
    env_var : str
        The environment variable name (e.g. ``ANVIL_DEVICE``).
    default_value : str
        The code-level default when no env or override is set.
    editable : bool
        Whether the user may override this setting via the UI.
    """

    def __init__(
        self,
        key: str,
        display_name: str,
        description: str,
        apply_class: ApplyClass,
        env_var: str,
        default_value: str,
        editable: bool = True,
    ) -> None:
        self.key = key
        self.display_name = display_name
        self.description = description
        self.apply_class = apply_class
        self.env_var = env_var
        self.default_value = default_value
        self.editable = editable


# ── Static setting catalog ──────────────────────────────────────────
# This is the single source of truth for every configurable runtime
# setting.  Add new settings here when introducing new config knobs.
CATALOG: list[CatalogEntry] = [
    CatalogEntry(
        key="port",
        display_name="Web Port",
        description="HTTP port the web server listens on.",
        apply_class=ApplyClass.BOOT_CRITICAL,
        env_var="ANVIL_PORT",
        default_value="8080",
    ),
    CatalogEntry(
        key="device",
        display_name="Compute Device",
        description="Device override (cpu, cuda:0, mps). Empty = auto.",
        apply_class=ApplyClass.APPLIES_LIVE,
        env_var="ANVIL_DEVICE",
        default_value="",
    ),
    CatalogEntry(
        key="mlflow_uri",
        display_name="MLflow URI",
        description="MLflow tracking server URI.",
        apply_class=ApplyClass.MLFLOW_RESTART,
        env_var="ANVIL_MLFLOW_URI",
        default_value="http://127.0.0.1:5001",
    ),
    CatalogEntry(
        key="mlflow_port",
        display_name="MLflow Port",
        description="Port parsed from the MLflow URI.",
        apply_class=ApplyClass.BOOT_CRITICAL,
        env_var="ANVIL_MLFLOW_URI",
        default_value="5001",
    ),
    CatalogEntry(
        key="log_dir",
        display_name="Log Directory",
        description="Directory for log files.",
        apply_class=ApplyClass.BOOT_CRITICAL,
        env_var="ANVIL_LOG_DIR",
        default_value="logs",
    ),
    CatalogEntry(
        key="storage_backend",
        display_name="Storage Backend",
        description="Storage backend name (local, s3).",
        apply_class=ApplyClass.BOOT_CRITICAL,
        env_var="ANVIL_STORAGE_BACKEND",
        default_value="local",
    ),
    CatalogEntry(
        key="db_auto_migrate",
        display_name="Auto Migrate",
        description="Auto-migrate DB schema on startup.",
        apply_class=ApplyClass.BOOT_CRITICAL,
        env_var="ANVIL_DB_AUTO_MIGRATE",
        default_value="true",
    ),
    CatalogEntry(
        key="content_dir",
        display_name="Content Directory",
        description="Directory for versioned content storage.",
        apply_class=ApplyClass.BOOT_CRITICAL,
        env_var="ANVIL_CONTENT_DIR",
        default_value="data/content",
    ),
    CatalogEntry(
        key="backup_dir",
        display_name="Backup Directory",
        description="Directory for deployment backups.",
        apply_class=ApplyClass.BOOT_CRITICAL,
        env_var="ANVIL_BACKUP_DIR",
        default_value="data/backups",
    ),
    CatalogEntry(
        key="backup_quota_bytes",
        display_name="Backup Quota",
        description="Maximum total bytes for all backups.",
        apply_class=ApplyClass.APPLIES_LIVE,
        env_var="ANVIL_BACKUP_QUOTA_BYTES",
        default_value=str(10 * 1024**3),
    ),
    CatalogEntry(
        key="backup_quota_warn_fraction",
        display_name="Backup Quota Warning",
        description="Fraction of quota that triggers a warning.",
        apply_class=ApplyClass.APPLIES_LIVE,
        env_var="ANVIL_BACKUP_QUOTA_WARN",
        default_value="0.8",
    ),
    CatalogEntry(
        key="backup_retention_max_count",
        display_name="Backup Max Count",
        description="Maximum number of backups to retain (empty = unlimited).",
        apply_class=ApplyClass.APPLIES_LIVE,
        env_var="ANVIL_BACKUP_RETENTION_MAX_COUNT",
        default_value="",
    ),
    CatalogEntry(
        key="backup_retention_max_age_days",
        display_name="Backup Max Age",
        description="Maximum age in days for retained backups (empty = unlimited).",
        apply_class=ApplyClass.APPLIES_LIVE,
        env_var="ANVIL_BACKUP_RETENTION_MAX_AGE_DAYS",
        default_value="",
    ),
    CatalogEntry(
        key="mlflow_disable_local",
        display_name="Disable Local MLflow",
        description="Do not start a local MLflow server.",
        apply_class=ApplyClass.BOOT_CRITICAL,
        env_var="ANVIL_MLFLOW_DISABLE_LOCAL",
        default_value="false",
    ),
]

# Build fast lookup dict.
_CATALOG_BY_KEY: dict[str, CatalogEntry] = {e.key: e for e in CATALOG}


def _resolve_env(entry: CatalogEntry) -> str | None:
    """Read the environment variable for a catalog entry.

    Parameters
    ----------
    entry : CatalogEntry
        The catalog entry whose ``env_var`` to check.

    Returns
    -------
    str or None
        The environment variable value, or ``None`` if unset.
    """
    return os.environ.get(entry.env_var)


def _resolve_env_config(entry: CatalogEntry) -> str:
    """Read the current effective value from the env-config dict.

    The ``anvil.config.get_config()`` function already resolves
    env vars into a flat dict.  We consult it so that any
    transformation (e.g. path resolution) is reflected.

    Parameters
    ----------
    entry : CatalogEntry
        The catalog entry whose key to look up.

    Returns
    -------
    str
        The stringified value from the env config dict.
    """
    cfg = get_env_config()
    raw = cfg.get(entry.key, "")
    if raw is None:
        return ""
    return str(raw)


class RuntimeConfigService:
    """Resolves runtime config through the override > env > default chain.

    Parameters
    ----------
    repo : RuntimeConfigRepository
        Repository for persisted override rows.
    """

    def __init__(self, repo: RuntimeConfigRepository) -> None:
        self._repo = repo

    def _resolve_value(
        self,
        entry: CatalogEntry,
        override: str | None,
    ) -> tuple[str, ConfigSource]:
        """Resolve the effective value and source for a catalog entry.

        Resolution order: override > env config dict > env var > default.

        Parameters
        ----------
        entry : CatalogEntry
            The catalog entry to resolve.
        override : str or None
            The persisted override value, if any.

        Returns
        -------
        tuple[str, ConfigSource]
            The effective value and its provenance source.
        """
        if override is not None:
            return override, ConfigSource.OVERRIDE
        env_config_value = _resolve_env_config(entry)
        if env_config_value and env_config_value != entry.default_value:
            return env_config_value, ConfigSource.ENV
        env_direct = _resolve_env(entry)
        if env_direct is not None:
            return env_direct, ConfigSource.ENV
        return entry.default_value, ConfigSource.DEFAULT

    async def get_all(
        self, boot_snapshot: dict[str, object] | None = None
    ) -> Sequence[ConfigSetting]:
        """Return all settings with resolved values.

        Parameters
        ----------
        boot_snapshot : dict or None
            Startup snapshot for precise ``pending_restart``
            computation.

        Returns
        -------
        Sequence[ConfigSetting]
            Every catalog entry as a ``ConfigSetting`` with the
            effective value and provenance resolved.
        """
        overrides_map: dict[str, str] = {}
        for row in await self._repo.get_all():
            overrides_map[row.key] = row.value

        results: list[ConfigSetting] = []
        for entry in CATALOG:
            override = overrides_map.get(entry.key)
            value, source = self._resolve_value(entry, override)
            results.append(
                ConfigSetting(
                    key=entry.key,
                    value=value,
                    source=source,
                    apply_class=entry.apply_class,
                    pending_restart=self._compute_pending_restart(
                        entry, source, value, boot_snapshot
                    ),
                    editable=entry.editable,
                    display_name=entry.display_name,
                    description=entry.description,
                    env_var=entry.env_var,
                    default_value=entry.default_value,
                )
            )
        return results

    async def get(
        self, key: str, boot_snapshot: dict[str, object] | None = None
    ) -> ConfigSetting | None:
        """Resolve a single setting by key.

        Parameters
        ----------
        key : str
            The setting key to resolve.
        boot_snapshot : dict or None
            Startup snapshot for precise ``pending_restart``
            computation.

        Returns
        -------
        ConfigSetting or None
            The resolved setting, or ``None`` if the key is not in
            the catalog.
        """
        entry = _CATALOG_BY_KEY.get(key)
        if entry is None:
            return None
        row = await self._repo.get(key)
        override = row.value if row is not None else None
        value, source = self._resolve_value(entry, override)
        return ConfigSetting(
            key=entry.key,
            value=value,
            source=source,
            apply_class=entry.apply_class,
            pending_restart=self._compute_pending_restart(
                entry, source, value, boot_snapshot
            ),
            editable=entry.editable,
            display_name=entry.display_name,
            description=entry.description,
            env_var=entry.env_var,
            default_value=entry.default_value,
        )

    def _compute_pending_restart(
        self,
        entry: CatalogEntry,
        source: ConfigSource,
        value: str,
        boot_snapshot: dict[str, object] | None,
    ) -> bool:
        """Determine whether a setting change is pending a restart.

        For ``BOOT_CRITICAL`` and ``MLFLOW_RESTART`` settings with a
        saved override: ``True`` only when the saved override differs
        from the startup snapshot value (US3/T049).  Falls back to
        marking any non-live override as pending when no snapshot is
        available.
        """
        if source != ConfigSource.OVERRIDE:
            return False
        if entry.apply_class == ApplyClass.APPLIES_LIVE:
            return False
        # If we have a startup snapshot, compare precisely.
        if boot_snapshot is not None and entry.key in boot_snapshot:
            return str(value) != str(boot_snapshot[entry.key])
        # Fallback: any non-live override is pending.
        return True

    async def set_override(self, key: str, value: str) -> ConfigSetting | None:
        """Persist a new override value for a setting.

        Records a ``CONFIG_SET`` audit event via the workbench.
        The caller is responsible for committing the session.

        Parameters
        ----------
        key : str
            The setting key.
        value : str
            The new value to persist.

        Returns
        -------
        ConfigSetting or None
            The updated setting, or ``None`` if the key is not in
            the catalog.

        Raises
        ------
        ValueError
            If the key is not editable or not in the catalog.
        """
        entry = _CATALOG_BY_KEY.get(key)
        if entry is None:
            raise ValueError(f"Unknown config key: {key}")
        if not entry.editable:
            raise ValueError(f"Config key is not editable: {key}")

        await self._repo.upsert(key, value, entry.apply_class.value)
        return await self.get(key)

    async def reset_override(self, key: str) -> ConfigSetting | None:
        """Remove a persisted override for a setting.

        Records a ``CONFIG_RESET`` audit event via the workbench.
        The setting reverts to its env/default value.

        Parameters
        ----------
        key : str
            The setting key to reset.

        Returns
        -------
        ConfigSetting or None
            The setting with the now-effective value, or ``None`` if
            the key is not in the catalog.

        Raises
        ------
        ValueError
            If the key is not editable or not in the catalog.
        """
        entry = _CATALOG_BY_KEY.get(key)
        if entry is None:
            raise ValueError(f"Unknown config key: {key}")
        if not entry.editable:
            raise ValueError(f"Config key is not editable: {key}")

        await self._repo.delete(key)
        return await self.get(key)

    @property
    def catalog(self) -> Mapping[str, CatalogEntry]:
        """Return the static setting catalog indexed by key."""
        return _CATALOG_BY_KEY
