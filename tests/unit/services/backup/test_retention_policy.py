"""Tests for RetentionPolicy — auto-rotation logic (FR-027, FR-032)."""

from datetime import datetime, timezone, UTC

from anvil.services.backup.retention_policy import RetentionPolicy


def _make_backup(
    backup_id: str,
    op_type: str = "backup",
    size: int = 100,
    age_days: int = 0,
):
    """Create a minimal backup-like object with the needed attrs."""
    return type(
        "FakeBackup",
        (),
        {
            "backup_id": backup_id,
            "operation_type": op_type,
            "archive_size_bytes": size,
            "created_at": datetime.now(UTC).replace(
                day=max(1, datetime.now(UTC).day - age_days)
            ),
        },
    )()


class TestRetentionPolicySafetyExemption:
    """Safety snapshots are never returned by the policy (FR-032)."""

    def test_never_returns_safety_snapshots(self):
        """Even if all backups are safety snapshots, none are returned."""
        policy = RetentionPolicy(quota_bytes=50)
        backups = [
            _make_backup("s1", op_type="pre_restore_safety", size=100),
            _make_backup("s2", op_type="pre_restore_safety", size=100),
        ]
        result = policy.select_for_rotation(backups, projected_size=10)
        assert result == []

    def test_skips_safety_snapshot_mixed(self):
        """Safety snapshots are skipped when mixed with regular backups."""
        policy = RetentionPolicy(quota_bytes=150)
        backups = [
            _make_backup("regular-1", size=100),
            _make_backup("safety-1", op_type="pre_restore_safety", size=100),
            _make_backup("regular-2", size=100),
        ]
        result = policy.select_for_rotation(backups, projected_size=10)
        # quota is 150, total is 200, projected is 210
        # should delete oldest regular (100 bytes), leaving 110 ≤ 150
        assert "safety-1" not in result


class TestRetentionPolicyQuota:
    """Quota-based rotation (FR-027)."""

    def test_no_rotation_when_under_quota(self):
        policy = RetentionPolicy(quota_bytes=500)
        backups = [_make_backup("a", size=100), _make_backup("b", size=100)]
        result = policy.select_for_rotation(backups, projected_size=50)
        # Total = 250, quota = 500, no rotation needed
        assert result == []

    def test_rotates_oldest_first_when_over_quota(self):
        """When projected total exceeds quota, oldest backups are deleted first."""
        policy = RetentionPolicy(quota_bytes=150)
        backups = [
            _make_backup("old", size=100, age_days=10),
            _make_backup("mid", size=100, age_days=5),
            _make_backup("new", size=100, age_days=1),
        ]
        result = policy.select_for_rotation(backups, projected_size=50)
        assert "old" in result
        # After deleting old (100): total = 250, projected_with_new = 250
        # After deleting old: remaining = 200 + 50 = 250, still over 150
        # Mid should also be deleted
        assert len(result) >= 1

    def test_empty_backups_list(self):
        policy = RetentionPolicy(quota_bytes=100)
        assert policy.select_for_rotation([], projected_size=50) == []


class TestRetentionPolicyMaxCount:
    """Count-based rotation (FR-032)."""

    def test_rotates_excess_count(self):
        policy = RetentionPolicy(quota_bytes=10000, max_count=2)
        backups = [
            _make_backup("a", size=10, age_days=5),
            _make_backup("b", size=10, age_days=3),
            _make_backup("c", size=10, age_days=1),
        ]
        result = policy.select_for_rotation(backups, projected_size=10)
        # 3 backups, max 2 → 1 should be deleted (the oldest)
        assert len(result) == 1
        assert "a" in result


class TestRetentionPolicyMaxAge:
    """Age-based rotation (FR-032)."""

    def test_rotates_older_than_max_age(self):
        """Backups older than max_age_days are rotated."""
        policy = RetentionPolicy(quota_bytes=10000, max_age_days=7)
        backups = [
            _make_backup("too-old", size=10, age_days=10),
            _make_backup("recent", size=10, age_days=1),
        ]
        result = policy.select_for_rotation(backups, projected_size=10)
        assert "too-old" in result
        assert "recent" not in result
