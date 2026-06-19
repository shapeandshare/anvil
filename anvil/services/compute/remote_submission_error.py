"""Exception for remote job submission failures.

Raised when a remote compute job cannot be submitted due to authentication,
network connectivity, or quota issues.
"""


class RemoteSubmissionError(Exception):
    """Raised when a remote job submission fails.

    Covers authentication failures, network connectivity errors, and quota
    exceeded conditions during submission of a compute job to a remote
    backend (e.g., Modal cloud GPUs).

    Parameters
    ----------
    args : tuple
        Variable-length argument list forwarded to ``Exception.__init__``.
        Typically a message describing the submission failure reason.
    """
