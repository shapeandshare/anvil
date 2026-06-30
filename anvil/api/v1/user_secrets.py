# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""API routes for per-user secrets management (feature 042).

Secrets are encrypted at rest (AES-256-GCM). The GET endpoint
returns key names only — never decrypted values.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from ...workbench import AnvilWorkbench
from ..deps import get_workbench

logger = logging.getLogger(__name__)

router = APIRouter()


class SetSecretBody(BaseModel):
    """Request body for ``POST /v1/user/secrets``."""

    model_config = ConfigDict(extra="forbid")

    key: str
    value: str


@router.get("/user/secrets")
async def list_secrets(
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, object]:
    """Return all secret key names for the current user.

    Never returns decrypted values. In local mode the user ID is
    a fixed session identifier; in SaaS mode it is the Cognito sub.
    """
    user_id = _current_user_id()
    keys = await workbench.user_secrets.list_keys(user_id)
    return {"data": keys}


@router.post("/user/secrets", status_code=201)
async def set_secret(
    body: SetSecretBody,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, object]:
    """Encrypt and store a secret for the current user."""
    user_id = _current_user_id()
    await workbench.user_secrets.set_secret(user_id, body.key, body.value)
    logger.info("Secret set for user %s (key length=%d)", user_id, len(body.key))
    return {"status": "created"}


@router.delete("/user/secrets")
async def delete_secret(
    key: str,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, object]:
    """Remove a secret for the current user."""
    user_id = _current_user_id()
    await workbench.user_secrets.delete_secret(user_id, key)
    return {"status": "deleted"}


def _current_user_id() -> str:
    """Return the current user identifier.

    In local mode all requests share a fixed user ID. In SaaS mode
    this would extract the Cognito sub from the JWT.
    """
    return "default"


########################################################################
# Admin: key rotation lifecycle (spec 058)
########################################################################


@router.post("/admin/secrets/rotate")
async def admin_rotate(
    wb: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, str]:
    """Trigger key rotation.

    Promotes the current key to previous and generates a new current
    key.  The caller must then run the re-encryption sweep and expire
    the previous key.

    Returns
    -------
    dict
        ``{"status": "accepted", "kid": "<new-key-id>"}``.
    """
    svc = wb.secret_rotation_service
    new_kid = await svc.rotate()
    return {"status": "accepted", "kid": new_kid}


@router.get("/admin/secrets/rotation-status")
async def admin_rotation_status(
    wb: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, object]:
    """Return the current ring state and per-kid row counts.

    Returns
    -------
    dict
        Dict with ``current``, ``previous``, and ``rows_by_kid`` keys.
    """
    svc = wb.secret_rotation_service
    return await svc.rotation_status_with_counts()


@router.post("/admin/secrets/sweep")
async def admin_sweep(
    wb: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, int]:
    """Trigger the re-encryption sweep.

    Re-encrypts all secrets still referencing the previous key under
    the current key.  Idempotent — re-running skips already-rotated
    rows.

    Returns
    -------
    dict
        ``{"rows_processed": <int>}``.
    """
    svc = wb.secret_rotation_service
    count = await svc.reencrypt_sweep()
    return {"rows_processed": count}


@router.post("/admin/secrets/expire-previous")
async def admin_expire_previous(
    wb: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, str | None]:
    """Expire the previous key.

    Removes the previous key from the ring.  Fails with
    ``SweepIncompleteError`` if residual rows still reference the
    previous key.

    Returns
    -------
    dict
        ``{"status": "ok"|"noop", "expired_kid": <str>|null}``.
    """
    svc = wb.secret_rotation_service
    expired = await svc.expire_previous()
    return {"status": "ok" if expired else "noop", "expired_kid": expired}
