# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Exception for persistent remote job polling failures.

Raised when repeated attempts to query the status of a remote compute job
have all failed. Not raised for transient failures that can be retried
internally.
"""


class RemotePollError(Exception):
    """Raised when polling a remote job fails persistently.

    Indicates that repeated attempts to query the status of a remote compute
    job have all failed (e.g., network timeout, lost job handle, remote
    service unavailable). Not raised for transient failures that can be
    retried internally.

    Parameters
    ----------
    args : tuple
        Variable-length argument list forwarded to ``Exception.__init__``.
        Typically a message describing the polling failure.
    """
