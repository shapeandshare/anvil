"""Tests for the BackupOperationType enum."""

from __future__ import annotations

from enum import StrEnum

from anvil.services.backup.backup_operation_type import BackupOperationType


class TestBackupOperationType:
    """BackupOperationType enum member values."""

    def test_member_values(self) -> None:
        """Each member should have the expected string value."""
        assert BackupOperationType.BACKUP.value == "backup"
        assert BackupOperationType.RESTORE.value == "restore"
        assert BackupOperationType.PRE_RESTORE_SAFETY.value == "pre_restore_safety"

    def test_members_are_str_enum(self) -> None:
        """Members should be StrEnum instances."""
        assert isinstance(BackupOperationType.BACKUP, StrEnum)

    def test_from_string_valid(self) -> None:
        """Converting a valid string should produce the enum member."""
        assert BackupOperationType("backup") is BackupOperationType.BACKUP
        assert BackupOperationType("restore") is BackupOperationType.RESTORE
        assert (
            BackupOperationType("pre_restore_safety")
            is BackupOperationType.PRE_RESTORE_SAFETY
        )

    def test_from_string_invalid_raises(self) -> None:
        """Converting an invalid string should raise ValueError."""
        try:
            BackupOperationType("unknown")
            assert False, "Expected ValueError"
        except ValueError:
            pass
