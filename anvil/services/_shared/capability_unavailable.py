# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Capability unavailable exception — raised when an MLflow capability is not supported.

Provides the ``CapabilityUnavailable`` exception class used by
``TrackingService`` when a requested MLflow capability (such as
managed evaluation datasets) is not available.
"""


class CapabilityUnavailable(Exception):
    """Raised when an MLflow capability (e.g. genai datasets) is unavailable."""

    pass
