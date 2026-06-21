# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Exception for unavailable compute backends.

Follows anvil's degraded-mode convention: non-fatal errors return empty values
and set ``self._degraded = True`` instead of raising. Only raise when the
caller explicitly opted into a capability that is missing (D4).
"""


class ComputeBackendUnavailable(Exception):
    """Raised when the user explicitly selected a backend that is not available.

    D4 rule: implicit capability upgrades (e.g. GPU -> CPU) silently fall back.
    This exception is ONLY raised for *explicit* selections that cannot be
    honoured -- it is never caught silently.

    Parameters
    ----------
    args : tuple
        Variable-length argument list forwarded to ``Exception.__init__``.
        Typically a human-readable message string describing which backend
        was unavailable and why.

    Examples
    --------
    >>> raise ComputeBackendUnavailable("Modal selected but not installed")
    """
