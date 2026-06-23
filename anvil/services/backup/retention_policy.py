# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Auto-rotation policy: selects which backups to delete when quota or
retention limits are exceeded.
"""

from collections.abc import Sequence
from datetime import datetime, UTC


class RetentionPolicy:
    """Determines which non-safety backups to rotate when storage is
    constrained.

    Safety snapshots (``pre_restore_safety``) are **never** returned by
    this policy, regardless of count or age.  Only normally deletable
    backups are eligible for rotation.

    Parameters
    ----------
    quota_bytes : int
        Maximum total bytes for backup archives.
    max_count : int or None
        Maximum number of non-safety backups to retain.  ``None`` means
        no limit (quota governs).
    max_age_days : int or None
        Maximum age in days for non-safety backups.  Backups older than
        this are rotated regardless of count/quota.  ``None`` means no
        age-based limit.
    """

    def __init__(
        self,
        quota_bytes: int,
        max_count: int | None = None,
        max_age_days: int | None = None,
    ) -> None:
        self._quota_bytes = quota_bytes
        self._max_count = max_count
        self._max_age_days = max_age_days

    def select_for_rotation(
        self,
        backups: Sequence[object],
        projected_size: int,
    ) -> list[str]:
        """Return backup ids (oldest first) whose deletion would bring
        storage within limits.

        Parameters
        ----------
        backups : Sequence[BackupOperation]
            All backup operations, ideally ordered by ``created_at``
            descending (newest first).  Each must have ``backup_id``,
            ``operation_type``, ``archive_size_bytes``, and
            ``created_at`` attributes.
        projected_size : int
            Estimated size of the new backup being created.

        Returns
        -------
        list[str]
            Ordered list of ``backup_id`` values to delete.  Empty if
            no rotation is needed.  Safety snapshots are never included.
        """
        if not backups:
            return []

        # Separate eligible backups from safety snapshots.
        eligible = [
            b
            for b in backups
            if getattr(b, "operation_type", "") != "pre_restore_safety"
        ]

        if not eligible:
            return []

        # Sort by created_at ascending (oldest first → rotate oldest).
        sorted_eligible = sorted(
            eligible,
            key=lambda b: (
                getattr(b, "created_at", datetime.min.replace(tzinfo=UTC))
                or datetime.min.replace(tzinfo=UTC)
            ),
        )

        total_existing = sum(
            getattr(b, "archive_size_bytes", 0) or 0 for b in sorted_eligible
        )
        projected_total = total_existing + projected_size
        to_delete: list[str] = []

        # Age-based rotation.
        now = datetime.now(UTC)
        if self._max_age_days is not None:
            (
                sorted_eligible[0].created_at.replace(tzinfo=UTC)
                if hasattr(sorted_eligible[0], "created_at")
                and sorted_eligible[0].created_at is not None
                else now
            )
            for b in list(sorted_eligible):
                created = getattr(b, "created_at", None)
                if created is None:
                    continue
                if created.tzinfo is None:
                    created = created.replace(tzinfo=UTC)
                age_days = (now - created).total_seconds() / 86400
                if age_days > self._max_age_days:
                    to_delete.append(b.backup_id)
                    sorted_eligible.remove(b)
                    total_existing -= getattr(b, "archive_size_bytes", 0) or 0
                    projected_total = total_existing + projected_size

        # Count-based rotation (remove oldest first).
        if self._max_count is not None and len(sorted_eligible) > self._max_count:
            excess = len(sorted_eligible) - self._max_count
            for b in sorted_eligible[:excess]:
                to_delete.append(b.backup_id)
                total_existing -= getattr(b, "archive_size_bytes", 0) or 0
            sorted_eligible = sorted_eligible[excess:]
            projected_total = total_existing + projected_size

        # Quota-based rotation.
        while projected_total > self._quota_bytes and sorted_eligible:
            oldest = sorted_eligible.pop(0)
            to_delete.append(oldest.backup_id)
            total_existing -= getattr(oldest, "archive_size_bytes", 0) or 0
            projected_total = total_existing + projected_size

        return to_delete
