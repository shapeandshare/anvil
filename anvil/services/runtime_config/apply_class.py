# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""How a config change is applied to the running instance."""

from __future__ import annotations

from enum import StrEnum


class ApplyClass(StrEnum):
    """Classification of how a configuration change takes effect.

    Determines the behaviour of the ``PUT /v1/config/{key}`` endpoint:

    ``BOOT_CRITICAL``
        The value is read at process start.  Editing marks it
        "pending restart"; the new value takes effect on the next
        instance start.
    ``MLFLOW_RESTART``
        The value controls the experiment-tracking sidecar.  The
        system auto-restarts that sidecar on save and reports the
        result.
    ``APPLIES_LIVE``
        The value is re-read on each request (no caching).  The
        change takes effect immediately after save with no restart
        required.
    """

    BOOT_CRITICAL = "boot_critical"
    MLFLOW_RESTART = "mlflow_restart"
    APPLIES_LIVE = "applies_live"
