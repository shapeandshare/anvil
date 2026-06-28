# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Provenance of a config setting's current value."""

from __future__ import annotations

from enum import StrEnum


class ConfigSource(StrEnum):
    """Where the effective value of a config setting came from.

    The resolution order is: ``OVERRIDE`` (persisted via UI/CLI) >
    ``ENV`` (environment variable) > ``DEFAULT`` (code-level built-in).
    """

    DEFAULT = "default"
    ENV = "env"
    OVERRIDE = "override"
