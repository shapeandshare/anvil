# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Runtime config CRUD API routes (User Story 2).

Provides endpoints for listing, reading, updating, and resetting
runtime configuration settings.  Audit events (CONFIG_SET,
CONFIG_RESET) are emitted at the route layer via the session-bound
``workbench.audit``.

MLFLOW_RESTART apply-class overrides trigger an automatic MLflow
sidecar restart (stop + start) on save.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from ...services.governance.audit_action import AuditAction
from ...services.governance.audit_outcome import AuditOutcome
from ...services.governance.audit_target_type import AuditTargetType
from ...services.runtime_config.apply_class import ApplyClass
from ...workbench import AnvilWorkbench
from ..deps import get_workbench
from .schemas_misc import ConfigSettingOut, UpdateConfigBody

router = APIRouter()


@router.get("/config")
async def list_config(
    request: Request,
    wb: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> list[ConfigSettingOut]:
    """Return all runtime configuration settings with resolved values.

    Parameters
    ----------
    request : Request
        FastAPI request object (provides ``app.state.boot_snapshot``).
    wb : AnvilWorkbench
        Session-bound workbench injected via FastAPI dependency.

    Returns
    -------
    list[ConfigSettingOut]
        Every catalog entry with the effective value, source,
        apply_class, editable flag, and pending-restart status.
    """
    boot_snapshot: dict[str, object] | None = getattr(
        request.app.state, "boot_snapshot", None
    )
    settings = await wb.runtime_config.get_all(boot_snapshot=boot_snapshot)
    return [
        ConfigSettingOut(
            key=s.key,
            value=s.value,
            source=s.source.value,
            apply_class=s.apply_class.value,
            pending_restart=s.pending_restart,
            editable=s.editable,
            display_name=s.display_name,
            description=s.description,
            env_var=s.env_var,
            default_value=s.default_value,
        )
        for s in settings
    ]


@router.get("/config/pending-restart")
async def list_pending_restart(
    request: Request,
    wb: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> list[ConfigSettingOut]:
    """Return only settings with a pending-restart flag.

    Reads the startup snapshot and current config overrides, then
    returns the diff — settings whose value has changed and whose
    ``apply_class`` is not ``applies_live``.

    Parameters
    ----------
    request : Request
        FastAPI request object (provides ``app.state.boot_snapshot``).
    wb : AnvilWorkbench
        Session-bound workbench injected via FastAPI dependency.

    Returns
    -------
    list[ConfigSettingOut]
        Every setting that has a pending restart.
    """
    boot_snapshot: dict[str, object] | None = getattr(
        request.app.state, "boot_snapshot", None
    )
    settings = await wb.runtime_config.get_all(boot_snapshot=boot_snapshot)
    return [
        ConfigSettingOut(
            key=s.key,
            value=s.value,
            source=s.source.value,
            apply_class=s.apply_class.value,
            pending_restart=s.pending_restart,
            editable=s.editable,
            display_name=s.display_name,
            description=s.description,
            env_var=s.env_var,
            default_value=s.default_value,
        )
        for s in settings
        if s.pending_restart
    ]


@router.get("/config/{key}")
async def get_config(
    key: str,
    wb: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> ConfigSettingOut:
    """Return a single runtime configuration setting by key.

    Parameters
    ----------
    key : str
        The setting key to retrieve.
    wb : AnvilWorkbench
        Session-bound workbench injected via FastAPI dependency.

    Returns
    -------
    ConfigSettingOut
        The resolved setting with value, source, and metadata.

    Raises
    ------
    HTTPException
        404 if the key is not in the catalog.
    """
    setting = await wb.runtime_config.get(key)
    if setting is None:
        raise HTTPException(status_code=404, detail=f"Unknown config key: {key}")
    return ConfigSettingOut(
        key=setting.key,
        value=setting.value,
        source=setting.source.value,
        apply_class=setting.apply_class.value,
        pending_restart=setting.pending_restart,
        editable=setting.editable,
        display_name=setting.display_name,
        description=setting.description,
        env_var=setting.env_var,
        default_value=setting.default_value,
    )


@router.put("/config/{key}")
async def update_config(
    key: str,
    body: UpdateConfigBody,
    request: Request,
    wb: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> ConfigSettingOut:
    """Set an override value for a runtime configuration setting.

    If the setting's ``apply_class`` is ``MLFLOW_RESTART`` the MLflow
    sidecar subprocess is automatically restart (stop + start) after
    persisting the override.

    Parameters
    ----------
    key : str
        The setting key to update.
    body : UpdateConfigBody
        The new value to persist.
    request : Request
        FastAPI request object (provides ``app.state.mlflow``).
    wb : AnvilWorkbench
        Session-bound workbench injected via FastAPI dependency.

    Returns
    -------
    ConfigSettingOut
        The updated setting with the newly overridden value.

    Raises
    ------
    HTTPException
        400 if the key is not editable, 404 if unknown.
    """
    try:
        result = await wb.runtime_config.set_override(key, body.value)
    except ValueError as exc:
        if "not editable" in str(exc) or "Unknown" in str(exc):
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        raise

    assert result is not None  # Assured by the ValueError guard above.

    # Auto-restart MLflow sidecar for MLFLOW_RESTART apply-class (T050).
    if result.apply_class == ApplyClass.MLFLOW_RESTART:
        mlflow = getattr(request.app.state, "mlflow", None)
        if mlflow is not None:
            if mlflow.is_running:
                mlflow.stop()
            mlflow.start()

    # Audit: config_set.
    await wb.audit.record(
        action_type=AuditAction.CONFIG_SET.value,
        target_type=AuditTargetType.RUNTIME_CONFIG.value,
        target_id=key,
        actor="ui",
        outcome=AuditOutcome.SUCCESS.value,
        params={"key": key, "value": body.value},
    )

    return ConfigSettingOut(
        key=result.key,
        value=result.value,
        source=result.source.value,
        apply_class=result.apply_class.value,
        pending_restart=result.pending_restart,
        editable=result.editable,
        display_name=result.display_name,
        description=result.description,
        env_var=result.env_var,
        default_value=result.default_value,
    )


@router.post("/config/{key}/reset")
async def reset_config(
    key: str,
    wb: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> ConfigSettingOut:
    """Remove an override for a runtime configuration setting.

    The setting reverts to its env or default value.

    Parameters
    ----------
    key : str
        The setting key to reset.
    wb : AnvilWorkbench
        Session-bound workbench injected via FastAPI dependency.

    Returns
    -------
    ConfigSettingOut
        The setting with the now-effective (reverted) value.

    Raises
    ------
    HTTPException
        400 if the key is not editable, 404 if unknown.
    """
    try:
        result = await wb.runtime_config.reset_override(key)
    except ValueError as exc:
        if "not editable" in str(exc) or "Unknown" in str(exc):
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        raise

    assert result is not None

    # Audit: config_reset.
    await wb.audit.record(
        action_type=AuditAction.CONFIG_RESET.value,
        target_type=AuditTargetType.RUNTIME_CONFIG.value,
        target_id=key,
        actor="ui",
        outcome=AuditOutcome.SUCCESS.value,
        params={"key": key},
    )

    return ConfigSettingOut(
        key=result.key,
        value=result.value,
        source=result.source.value,
        apply_class=result.apply_class.value,
        pending_restart=result.pending_restart,
        editable=result.editable,
        display_name=result.display_name,
        description=result.description,
        env_var=result.env_var,
        default_value=result.default_value,
    )
