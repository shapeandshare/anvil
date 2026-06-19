"""Result type for audit-chain integrity verification.

Returned by :meth:`AuditService.verify_chain` after recomputing
each entry's hash and checking the ``prev_hash`` linkage.
"""

from pydantic import BaseModel


class ChainVerifyResult(BaseModel):
    """Outcome of an audit-chain integrity check.

    Parameters
    ----------
    valid : bool
        ``True`` when the entire chain is intact (every entry's
        ``entry_hash`` recomputes correctly and links to the next).
    break_at_sequence : int | None
        The first ``sequence`` where a break was detected, or
        ``None`` when *valid* is ``True``.
    entries_checked : int
        Number of entries verified.
    """

    valid: bool
    break_at_sequence: int | None = None
    entries_checked: int = 0