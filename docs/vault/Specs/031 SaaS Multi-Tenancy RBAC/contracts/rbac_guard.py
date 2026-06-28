# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""RBAC guard interface and cluster-admin action matrix contract.

Defines the permission-check seam between the RBAC resolution middleware
and the service layer. The guard is called before any write/mutate
operation; it checks whether the caller's effective role and/or
is_cluster_admin flag permits the requested action.

Note: design contract artifact — targets Python 3.11+.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Protocol


class Action(StrEnum):
    """Actions that may be gated by the RBAC guard."""

    # Resource CRUD
    READ = "read"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"

    # Membership management
    INVITE_MEMBER = "invite_member"
    REMOVE_MEMBER = "remove_member"
    ASSIGN_ROLE = "assign_role"

    # Team management
    CREATE_TEAM = "create_team"
    DELETE_TEAM = "delete_team"

    # Organization lifecycle
    DELETE_ORG = "delete_org"
    SUSPEND_ORG = "suspend_org"
    REACTIVATE_ORG = "reactivate_org"

    # Cluster operations (cluster-admin only)
    VIEW_HEALTH = "view_health"
    VIEW_LOGS = "view_logs"
    CANCEL_JOB = "cancel_job"
    MANAGE_CLUSTER_ADMINS = "manage_cluster_admins"
    VIEW_CROSS_ORG_USAGE = "view_cross_org_usage"


class RBACContext(Protocol):
    """Protocol for the resolved RBAC context attached to a request.

    Implemented by the RBAC resolution middleware (anvil/_saas/auth/rbac.py).
    """

    user_id: int
    org_id: int | None  # None in local mode
    is_cluster_admin: bool
    effective_role: str | None  # OrgRole value or None in local mode


class RBACGuard(ABC):
    """Service-layer permission guard.

    Called before write/mutate operations. Throws PermissionError (or
    returns False) if the action is not permitted.

    In local mode (FR-038b), all checks MUST pass unconditionally —
    effective_role is None and is_cluster_admin is ignored.
    """

    @abstractmethod
    async def check(
        self,
        ctx: RBACContext,
        action: Action,
        resource_owner_org_id: int | None = None,
    ) -> bool:
        """Check whether the caller may perform `action`.

        Parameters
        ----------
        ctx : RBACContext
            Resolved caller context from middleware.
        action : Action
            The action to gate.
        resource_owner_org_id : int | None, optional
            The org that owns the target resource. None for org-level
            actions.

        Returns
        -------
        bool
            True if permitted, False if denied.

        Raises
        ------
        PermissionError
            If the action is denied and a raising API is preferred.
        """

    @abstractmethod
    async def require(
        self,
        ctx: RBACContext,
        action: Action,
        resource_owner_org_id: int | None = None,
    ) -> None:
        """Like check() but raises PermissionError on denial.

        Parameters
        ----------
        ctx : RBACContext
            Resolved caller context from middleware.
        action : Action
            The action to gate.
        resource_owner_org_id : int | None, optional
            The org that owns the target resource.

        Raises
        ------
        PermissionError
            If the action is not permitted.
        """


# Implementation lives at anvil/services/auth/guard.py
# RBAC resolution middleware lives at anvil/_saas/auth/rbac.py
