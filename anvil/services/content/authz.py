"""Content repository authorization — management-action guard.

In local single-user mode all management actions are permitted.
This is the injection seam for multi-principal RBAC (FR-036)
in the future SaaS delivery.

See Also
--------
ADR-033 : Content repository substrate
docs/vault/Specs/019 LakeFS Content Repo/spec.md : US2 authorization
"""

from __future__ import annotations

from fastapi import Depends

from ...api.deps import get_workbench
from ...workbench import AnvilWorkbench


class AuthzContext:
    """Per-request authorization context for content management actions.

    Provides a ``require_management_action`` guard that trivially
    passes in local single-user mode.  In the future SaaS delivery
    this is the injection point for org/team/role verification
    against the caller's principal.

    Parameters
    ----------
    workbench : AnvilWorkbench
        Session-bound workbench providing repository access for
        future authorization queries.
    """

    def __init__(self, workbench: AnvilWorkbench) -> None:
        self._workbench = workbench

    def require_management_action(self, action: str) -> None:
        """Assert that the caller may perform a management action.

        In local single-user mode all management actions are
        permitted (``rename``, ``tag``, ``compose``, ``promote``,
        ``lock``).  SaaS builds on this by injecting org/team/role
        checks.

        Parameters
        ----------
        action : str
            Human-readable action name for error messages
            (e.g. ``"rename"``, ``"tag"``).  Used in future SaaS
            audit log entries and authorization-denied responses.

        Raises
        ------
        HTTPException
            If the caller is not authorized (never raised in local
            mode — reserved for SaaS enforcement).
        """
        _ = action  # consumed by future SaaS auth check


async def require_content_auth(
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> AuthzContext:
    """FastAPI dependency that provides a content-auth context.

    Use as a dependency in content-management route handlers::

        @router.post("/content/corpora/{id}/lock")
        async def lock_corpus(
            id: int,
            auth: AuthzContext = Depends(require_content_auth),
        ):
            auth.require_management_action("lock")
            ...

    Parameters
    ----------
    workbench : AnvilWorkbench
        Session-bound workbench, injected via FastAPI's
        ``Depends(get_workbench)``.

    Returns
    -------
    AuthzContext
        A per-request authorization context ready to guard
        management actions.
    """
    return AuthzContext(workbench)
