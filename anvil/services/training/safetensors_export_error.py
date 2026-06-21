# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Safetensors export error exception.

Provides the ``SafetensorsExportError`` exception class raised when
safetensors model export fails.
"""


class SafetensorsExportError(Exception):
    """Raised when safetensors export fails."""

    pass
