# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""A single configuration setting with its value, provenance, and
apply-classification.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .apply_class import ApplyClass
from .config_source import ConfigSource


class ConfigSetting(BaseModel):
    """A single configuration setting as returned to the API/UI.

    Parameters
    ----------
    key : str
        The setting name (e.g. ``rate_limit``, ``device``).
    value : str
        The current effective value (stringified).
    source : ConfigSource
        Provenance — ``override``, ``env``, or ``default``.
    apply_class : ApplyClass
        How changes to this setting are applied.
    pending_restart : bool
        ``True`` when a boot-critical override has been saved but not
        yet applied (the process is still using the prior value).
    editable : bool
        ``True`` when the setting can be overridden via the UI.
    """

    key: str
    value: str
    source: ConfigSource
    apply_class: ApplyClass = ApplyClass.APPLIES_LIVE
    pending_restart: bool = Field(default=False)
    editable: bool = Field(default=True)
