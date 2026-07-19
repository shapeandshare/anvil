# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Feedback annotation type enumeration."""

from __future__ import annotations

from enum import StrEnum


class AnnotationType(StrEnum):
    """Visual annotation types available on a feedback report.

    Attributes
    ----------
    ELEMENT : str
        Highlight a specific DOM element (``"element"``).
    CIRCLE : str
        Draw a circle/ellipse over a region (``"circle"``).
    FREEHAND : str
        Freeform drawing over a region (``"freehand"``).
    """

    ELEMENT = "element"
    CIRCLE = "circle"
    FREEHAND = "freehand"
