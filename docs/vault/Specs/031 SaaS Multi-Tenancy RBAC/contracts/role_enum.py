# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Role enumeration and permission matrix for anvil's RBAC system.

Defines the four org-scoped roles (owner, admin, member, viewer) and the
cluster-admin flag semantics. The permission matrix maps role → action
allow/deny. In local mode (FR-038b) the role system is bypassed entirely.

Note: design contract artifact — targets Python 3.11+ (StrEnum).
"""

from __future__ import annotations

from enum import StrEnum


class OrgRole(StrEnum):
    """Organization-scoped RBAC role.

    Each user has exactly one org role via their Membership record.
    A TeamMembership MAY override the role within a specific team.
    """

    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


# Permission matrix: Action → minimum required role.
# Effective role = team role_override if present, else org Membership.role.
#
# | Action                        | owner | admin | member | viewer |
# |-------------------------------|:-----:|:-----:|:------:|:------:|
# | Read org resources            |   ✅  |   ✅  |   ✅   |   ✅   |
# | Create corpus/dataset/job     |   ✅  |   ✅  |   ✅   |   ❌   |
# | Delete own resources          |   ✅  |   ✅  |   ✅   |   ❌   |
# | Delete any org resource       |   ✅  |   ✅  |   ❌   |   ❌   |
# | Invite/remove members         |   ✅  |   ✅  |   ❌   |   ❌   |
# | Create/delete teams           |   ✅  |   ✅  |   ❌   |   ❌   |
# | Assign roles                  |   ✅  |   ❌  |   ❌   |   ❌   |
# | Delete organization           |   ✅  |   ❌  |   ❌   |   ❌   |
# | View usage/billing            |   ✅  |   ✅  |   ❌   |   ❌   |

# Cluster-admin flag (is_cluster_admin on users table):
# - READ/LIST: bypasses org_id scoping — returns cross-org data (read-wide)
# - WRITE/MUTATE: does NOT bypass org-role guard (write-narrow)
# - Grants the fixed cluster-operation action matrix (FR-037b):
#   - Suspend/reactivate organizations
#   - Create/remove cluster admins
#   - View health, logs, cross-org usage/billing
#   - Cancel any running training job
# - Is orthogonal to OrgRole — a user may be both cluster_admin and an org member
#
# Local mode (FR-038b): no auth, no role check, all queries unfiltered.
