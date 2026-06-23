"""Tests for SnapshotPlanner — managed roots, exclusions, pre-flight."""

from pathlib import Path, PosixPath

from anvil.services.backup.snapshot_planner import SnapshotPlan, SnapshotPlanner


class TestSnapshotPlannerRoots:
    """Verify the hardcoded root lists (FR-001, R14)."""

    def test_includes_all_deployment_roots(self):
        assert "data/anvil-state.db" in SnapshotPlanner.INCLUDED_ROOTS
        assert "data/models" in SnapshotPlanner.INCLUDED_ROOTS
        assert "data/datasets" in SnapshotPlanner.INCLUDED_ROOTS
        assert "data/storage" in SnapshotPlanner.INCLUDED_ROOTS
        assert "data/content" in SnapshotPlanner.INCLUDED_ROOTS
        assert "mlruns" in SnapshotPlanner.INCLUDED_ROOTS

    def test_excludes_logs_and_env(self):
        assert "logs" in SnapshotPlanner.EXCLUDED_ROOTS
        assert ".env" in SnapshotPlanner.EXCLUDED_ROOTS

    def test_num_roots(self):
        """6 managed roots + 2 exclusions."""
        assert len(SnapshotPlanner.INCLUDED_ROOTS) == 6
        assert len(SnapshotPlanner.EXCLUDED_ROOTS) == 2


class TestSnapshotPlannerPlan:
    """Plan method behavior (tests run in repo root with real dirs)."""

    def test_plan_returns_snapshot_plan(self, tmp_path: PosixPath):
        planner = SnapshotPlanner()
        result = planner.plan(backup_dir=tmp_path, quota_bytes=10 * 1024**3)
        assert isinstance(result, SnapshotPlan)
        assert isinstance(result.roots, list)
        assert result.total_estimated_bytes >= 0
        assert result.required_free_bytes >= 0
        assert isinstance(result.sufficient_space, bool)

    def test_plan_does_not_include_excluded_roots(self, tmp_path: PosixPath):
        """An explicit check that excluded roots (data/backups, .env) are
        not in the INCLUDED_ROOTS — they should not appear in archive entries
        even if they exist on disk."""
        planner = SnapshotPlanner()
        for rel in SnapshotPlanner.EXCLUDED_ROOTS:
            assert rel not in SnapshotPlanner.INCLUDED_ROOTS