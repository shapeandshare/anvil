# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chat template status enumeration for template lifecycle."""

from __future__ import annotations

from enum import StrEnum


class ChatTemplateStatus(StrEnum):
    """Lifecycle state of a chat template.

    Attributes
    ----------
    ACTIVE : str
        Template is available for use (``"active"``).
    DEPRECATED : str
        Template is deprecated and should not be used for new preparations;
        existing ``FineTuneDataset`` references remain valid
        (``"deprecated"``).
    """

    ACTIVE = "active"
    DEPRECATED = "deprecated"
