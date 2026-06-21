# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Advisory checkout lock state enumeration."""

from enum import StrEnum


class LockState(StrEnum):
    """State of an advisory checkout lock.

    Attributes
    ----------
    HELD : str
        Lock is actively held (``"held"``).
    RELEASED : str
        Lock has been released (``"released"``).
    """

    HELD = "held"
    RELEASED = "released"
