# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Outcomes of audited lifecycle events.

Records whether an action completed successfully, was rejected by
a gate, or encountered an error.
"""

from enum import StrEnum


class AuditOutcome(StrEnum):
    """Outcome of an audited action.

    Values
    ------
    SUCCESS
        The action completed without error.
    REJECTED
        The action was rejected (e.g. by the acceptable-use gate).
    ERROR
        The action encountered an error and did not complete.
    """

    SUCCESS = "success"
    REJECTED = "rejected"
    ERROR = "error"
