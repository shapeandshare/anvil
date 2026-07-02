# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Resolved compute backend identifier enumeration."""

from enum import StrEnum


class ComputeBackendResult(StrEnum):
    """Resolved compute backend identifier stored in result objects.

    Attributes
    ----------
    LOCAL : str
        Local execution (``"local"``).
    MODAL : str
        Modal cloud GPU execution (``"modal"``).
    SAAS : str
        SaaS batch compute execution (``"saas"``).
    """

    LOCAL = "local"
    MODAL = "modal"
    SAAS = "saas"
