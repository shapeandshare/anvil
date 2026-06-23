# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Entity types that can be audit targets.

Audit entries reference a ``target_type`` indicating what kind of
entity the event pertains to.  This avoids hard foreign-key
relationships so that audit entries outlive their targets (e.g. a
``delete`` event still exists after the entity is removed).
"""

from enum import StrEnum


class AuditTargetType(StrEnum):
    """Entity types that can appear as the target of an audit event.

    Values
    ------
    DATASET
        A training dataset.
    CORPUS
        A training corpus.
    SAMPLE
        An individual sample within a dataset.
    POLICY
        The acceptable-use / no-harm governance policy.
    AUDIT_CHAIN
        The audit chain itself (for checkpoint events).
    """

    DATASET = "dataset"
    CORPUS = "corpus"
    SAMPLE = "sample"
    POLICY = "policy"
    AUDIT_CHAIN = "audit_chain"
    BACKUP = "backup"
