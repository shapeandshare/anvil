# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Training stop exception — raised when the user requests a stop.

Provides the ``StopRequested`` exception class used by ``TrainingService``
to signal that training should be halted.
"""


class StopRequested(Exception):
    """Raised when training is requested to stop by the user."""

    pass
