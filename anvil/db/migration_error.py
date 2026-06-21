# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Custom exception for database migration failures.

Provides ``MigrationError``, a ``RuntimeError`` subclass that carries
revision context to help diagnose schema drift.
"""


class MigrationError(RuntimeError):
    """Raised when a migration operation fails or schema is out of date.

    Attributes
    ----------
    current_rev : str or None
        The current database revision at the time of the error.
    head_rev : str or None
        The expected HEAD revision at the time of the error.
    """

    def __init__(
        self, message: str, current_rev: str | None = None, head_rev: str | None = None
    ):
        """Initialise the error with revision context.

        Parameters
        ----------
        message : str
            Human-readable error description.
        current_rev : str, optional
            Current database revision hash. Defaults to ``None``.
        head_rev : str, optional
            Expected HEAD revision hash. Defaults to ``None``.
        """
        self.current_rev = current_rev
        self.head_rev = head_rev
        super().__init__(message)
