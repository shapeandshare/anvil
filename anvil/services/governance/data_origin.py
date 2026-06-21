# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Origin classification for data provenance records.

Distinguishes whether a dataset or corpus originated from bundled
sample data shipped with the application, or from user-supplied
content (uploaded, imported, or pasted).
"""

from enum import StrEnum


class DataOrigin(StrEnum):
    """Classification of where a dataset or corpus originated.

    ``BUNDLED``
        Data that ships with the application (read-only sample data).
    ``USER``
        Data uploaded, imported, or pasted by the user.
    """

    BUNDLED = "bundled"
    USER = "user"
