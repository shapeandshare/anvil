# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Types of auditable lifecycle events.

Each member corresponds to a distinct action type tracked in the
:class:`AuditEvent` hash-chained trail. Values are stored as
lower-case snake_case strings.
"""

from enum import StrEnum


class AuditAction(StrEnum):
    """Types of lifecycle events recorded in the audit trail.

    Values
    ------
    SEED
        Bundled sample data was seeded on first run.
    UPLOAD
        A user uploaded a dataset.
    IMPORT
        Text was imported into an existing dataset.
    CURATE
        A curation operation (dedup, filter, edit, replace) ran.
    DELETE
        A dataset or corpus was deleted.
    TAKEDOWN
        Data was removed via a takedown request.
    POLICY_ACCEPT
        A submission passed the acceptable-use gate.
    POLICY_REJECT
        A submission was rejected by the acceptable-use gate.
    CHAIN_CHECKPOINT
        A manual checkpoint / archival marker on the audit chain.
    """

    SEED = "seed"
    UPLOAD = "upload"
    IMPORT = "import"
    CURATE = "curate"
    DELETE = "delete"
    TAKEDOWN = "takedown"
    POLICY_ACCEPT = "policy_accept"
    POLICY_REJECT = "policy_reject"
    CHAIN_CHECKPOINT = "chain_checkpoint"
