# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""SSE progress event emitted during long-running backup/restore ops."""

from pydantic import BaseModel


class ProgressEvent(BaseModel):
    """A single server-sent event payload for backup/restore progress.

    Parameters
    ----------
    event : str
        Event type: ``progress``, ``complete``, ``error``, or
        ``heartbeat``.
    operation_type : str
        ``backup`` or ``restore``.
    backup_id : str or None
        The operation's backup id once known.
    percent : float
        0.0 to 100.0.
    current_step : str
        Human-readable step label (e.g. "Snapshotting database").
    message : str or None
        Error detail or info message.
    safety_snapshot_id : str or None
        Set on restore-complete to provide an undo reference.
    """

    event: str = "progress"
    operation_type: str = "backup"
    backup_id: str | None = None
    percent: float = 0.0
    current_step: str = ""
    message: str | None = None
    safety_snapshot_id: str | None = None
