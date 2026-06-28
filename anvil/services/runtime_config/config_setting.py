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
    display_name : str
        Human-readable label for the UI.
    description : str
        Brief description of what this setting controls.
    env_var : str
        The environment variable name (e.g. ``ANVIL_DEVICE``).
    default_value : str
        The code-level default when no env or override is set.
    """

    key: str
    value: str
    source: ConfigSource
    apply_class: ApplyClass = ApplyClass.APPLIES_LIVE
    pending_restart: bool = Field(default=False)
    editable: bool = Field(default=True)
    display_name: str = Field(default="")
    description: str = Field(default="")
    env_var: str = Field(default="")
    default_value: str = Field(default="")
