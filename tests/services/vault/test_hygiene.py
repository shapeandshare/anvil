# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for hygiene module — tag conformity, frontmatter completeness."""

from __future__ import annotations

from pathlib import Path

from anvil.services.vault.hygiene import compute_hygiene
from anvil.services.vault.scanner import GraphHealthRunner


def _run_hygiene(test_vault_dir: Path):
    runner = GraphHealthRunner(test_vault_dir, test_vault_dir)
    runner.scan_all_notes()
    return compute_hygiene(runner.notes, test_vault_dir)


class TestHygiene:
    """Tests for ``compute_hygiene``."""

    def test_tag_conformity(self, test_vault_dir: Path) -> None:
        metrics = _run_hygiene(test_vault_dir)
        # InvalidNote has type/unknown and status/fake — should be non-conformant
        assert len(metrics.non_conformant_tags) > 0

    def test_frontmatter_completeness(self, test_vault_dir: Path) -> None:
        metrics = _run_hygiene(test_vault_dir)
        # InvalidNote is missing required fields
        assert len(metrics.missing_fields) > 0

    def test_phantom_links(self, test_vault_dir: Path) -> None:
        metrics = _run_hygiene(test_vault_dir)
        # InvalidNote links to NonexistentTarget — should be a phantom link
        phantoms = [p for p in metrics.phantom_links if "NonexistentTarget" in p]
        assert len(phantoms) > 0
