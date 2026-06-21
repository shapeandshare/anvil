# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Source kind enumeration for content origins."""

from enum import StrEnum


class SourceKind(StrEnum):
    """Categorisation of a content source.

    Attributes
    ----------
    INJECTOR : str
        Automated system that pushes content (``"injector"``).
    IMPORTER : str
        Import job that pulls content from an external source
        (``"importer"``).
    MANUAL : str
        Human-curated upload or manual entry (``"manual"``).
    """

    INJECTOR = "injector"
    IMPORTER = "importer"
    MANUAL = "manual"
