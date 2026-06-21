# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for compute_manifest_digest canonical digest stability.

Tests the four core properties of the manifest digest function:

- **Stability**: output is a lower-case hex string of exactly 64 characters
  (SHA-256).
- **Immutability property**: changing any entry field (path, content_hash,
  weight, source) produces a different digest.
- **Sorted-key guarantee**: reordering identical entries produces the same
  digest (entries are sorted by ``(path, content_hash)`` before hashing).
- **Determinism**: identical inputs always produce identical outputs.
"""

from __future__ import annotations

import hashlib
import json

from anvil.services.content.manifest import (
    Manifest,
    ManifestEntry,
    compute_manifest_digest,
)


class TestManifestDigestStability:
    """Tests that compute_manifest_digest returns a valid SHA-256 hex string."""

    def test_returns_64_char_hex_string(self) -> None:
        """Digest output is always a 64-character lower-case hex string."""
        manifest = Manifest(
            corpus_slug="test-corpus",
            version_number=1,
            entries=[
                ManifestEntry(path="a.txt", content_hash="aa" * 32, weight=1.0),
            ],
        )
        digest = compute_manifest_digest(manifest)
        assert isinstance(digest, str)
        assert len(digest) == 64
        # Verify it's valid hex
        int(digest, 16)

    def test_uses_sha256_algorithm(self) -> None:
        """Digest is computed via SHA-256, verifiable by re-computing manually."""
        manifest = Manifest(
            corpus_slug="sha-test",
            version_number=1,
            entries=[
                ManifestEntry(path="f.txt", content_hash="bb" * 32, weight=2.0),
            ],
        )
        digest = compute_manifest_digest(manifest)

        # Manually replicate the algorithm.
        sorted_entries = sorted(
            manifest.entries, key=lambda e: (e.path, e.content_hash)
        )
        data = manifest.model_dump()
        data["entries"] = [e.model_dump() for e in sorted_entries]
        canonical = json.dumps(
            data, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        )
        expected = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

        assert digest == expected

    def test_empty_entries_produces_valid_digest(self) -> None:
        """An empty-entry-list manifest still produces a valid digest."""
        manifest = Manifest(
            corpus_slug="empty",
            version_number=1,
        )
        digest = compute_manifest_digest(manifest)
        assert len(digest) == 64
        int(digest, 16)


class TestManifestDigestImmutability:
    """Tests that any entry change produces a different digest."""

    def test_changing_path_changes_digest(self) -> None:
        """Different path → different digest."""
        base = Manifest(
            corpus_slug="s",
            version_number=1,
            entries=[ManifestEntry(path="a.txt", content_hash="aa" * 32)],
        )
        modified = Manifest(
            corpus_slug="s",
            version_number=1,
            entries=[ManifestEntry(path="b.txt", content_hash="aa" * 32)],
        )
        assert compute_manifest_digest(base) != compute_manifest_digest(modified)

    def test_changing_content_hash_changes_digest(self) -> None:
        """Different content_hash → different digest."""
        base = Manifest(
            corpus_slug="s",
            version_number=1,
            entries=[ManifestEntry(path="a.txt", content_hash="aa" * 32)],
        )
        modified = Manifest(
            corpus_slug="s",
            version_number=1,
            entries=[ManifestEntry(path="a.txt", content_hash="bb" * 32)],
        )
        assert compute_manifest_digest(base) != compute_manifest_digest(modified)

    def test_changing_weight_changes_digest(self) -> None:
        """Different weight (non-default) → different digest."""
        base = Manifest(
            corpus_slug="s",
            version_number=1,
            entries=[ManifestEntry(path="a.txt", content_hash="aa" * 32, weight=1.0)],
        )
        modified = Manifest(
            corpus_slug="s",
            version_number=1,
            entries=[ManifestEntry(path="a.txt", content_hash="aa" * 32, weight=2.5)],
        )
        assert compute_manifest_digest(base) != compute_manifest_digest(modified)

    def test_changing_source_changes_digest(self) -> None:
        """Different source → different digest."""
        base = Manifest(
            corpus_slug="s",
            version_number=1,
            entries=[ManifestEntry(path="a.txt", content_hash="aa" * 32, source=None)],
        )
        modified = Manifest(
            corpus_slug="s",
            version_number=1,
            entries=[
                ManifestEntry(path="a.txt", content_hash="aa" * 32, source="injector-x")
            ],
        )
        assert compute_manifest_digest(base) != compute_manifest_digest(modified)

    def test_adding_entry_changes_digest(self) -> None:
        """Adding an entry → different digest."""
        single = Manifest(
            corpus_slug="s",
            version_number=1,
            entries=[ManifestEntry(path="a.txt", content_hash="aa" * 32)],
        )
        two = Manifest(
            corpus_slug="s",
            version_number=1,
            entries=[
                ManifestEntry(path="a.txt", content_hash="aa" * 32),
                ManifestEntry(path="b.txt", content_hash="bb" * 32),
            ],
        )
        assert compute_manifest_digest(single) != compute_manifest_digest(two)

    def test_removing_entry_changes_digest(self) -> None:
        """Removing an entry → different digest."""
        two = Manifest(
            corpus_slug="s",
            version_number=1,
            entries=[
                ManifestEntry(path="a.txt", content_hash="aa" * 32),
                ManifestEntry(path="b.txt", content_hash="bb" * 32),
            ],
        )
        one = Manifest(
            corpus_slug="s",
            version_number=1,
            entries=[ManifestEntry(path="b.txt", content_hash="bb" * 32)],
        )
        assert compute_manifest_digest(two) != compute_manifest_digest(one)

    def test_changing_corpus_slug_changes_digest(self) -> None:
        """Different corpus_slug → different digest (metadata matters)."""
        base = Manifest(
            corpus_slug="corpus-a",
            version_number=1,
            entries=[ManifestEntry(path="x.txt", content_hash="aa" * 32)],
        )
        modified = Manifest(
            corpus_slug="corpus-b",
            version_number=1,
            entries=[ManifestEntry(path="x.txt", content_hash="aa" * 32)],
        )
        assert compute_manifest_digest(base) != compute_manifest_digest(modified)

    def test_changing_chunk_cfg_changes_digest(self) -> None:
        """Different chunk_cfg → different digest."""
        base = Manifest(
            corpus_slug="s",
            version_number=1,
            chunk_cfg={"strategy": "line", "block_size": 128},
            entries=[ManifestEntry(path="a.txt", content_hash="aa" * 32)],
        )
        modified = Manifest(
            corpus_slug="s",
            version_number=1,
            chunk_cfg={"strategy": "windowed", "block_size": 256},
            entries=[ManifestEntry(path="a.txt", content_hash="aa" * 32)],
        )
        assert compute_manifest_digest(base) != compute_manifest_digest(modified)


class TestManifestDigestOrdering:
    """Tests that reordering entries is transparent to the digest."""

    def test_reordered_entries_same_digest(self) -> None:
        """Reordering identical entries produces the same digest."""
        entries = [
            ManifestEntry(path="b.txt", content_hash="bb" * 32),
            ManifestEntry(path="a.txt", content_hash="aa" * 32),
            ManifestEntry(path="c.txt", content_hash="cc" * 32),
        ]
        reversed_entries = list(reversed(entries))

        m1 = Manifest(corpus_slug="s", version_number=1, entries=entries)
        m2 = Manifest(corpus_slug="s", version_number=1, entries=reversed_entries)

        assert compute_manifest_digest(m1) == compute_manifest_digest(m2)

    def test_shuffled_entries_same_digest(self) -> None:
        """Multiple random-ish orderings of the same entry set → same digest."""
        entries = [
            ManifestEntry(path="z.txt", content_hash="zz" * 32),
            ManifestEntry(path="a.txt", content_hash="aa" * 32),
            ManifestEntry(path="m.txt", content_hash="mm" * 32),
            ManifestEntry(path="f.txt", content_hash="ff" * 32),
        ]

        import itertools

        digests: set[str] = set()
        for perm in itertools.islice(itertools.permutations(entries), 12):
            m = Manifest(corpus_slug="s", version_number=1, entries=list(perm))
            digests.add(compute_manifest_digest(m))

        assert len(digests) == 1, (
            f"Expected all permutations to produce the same digest, "
            f"but got {len(digests)} different digests"
        )

    def test_same_path_different_hash_ordering(self) -> None:
        """Entries with same path but different content_hashes are
        sorted by content_hash, making ordering irrelevant.
        """
        entries = [
            ManifestEntry(path="a.txt", content_hash="cc" * 32),
            ManifestEntry(path="a.txt", content_hash="aa" * 32),
            ManifestEntry(path="a.txt", content_hash="bb" * 32),
        ]
        reversed_entries = list(reversed(entries))

        m1 = Manifest(corpus_slug="s", version_number=1, entries=entries)
        m2 = Manifest(corpus_slug="s", version_number=1, entries=reversed_entries)

        assert compute_manifest_digest(m1) == compute_manifest_digest(m2)


class TestManifestDigestDeterminism:
    """Tests that the function is purely deterministic."""

    def test_same_inputs_same_output(self) -> None:
        """Calling twice on the same manifest yields the same digest."""
        manifest = Manifest(
            corpus_slug="deterministic",
            version_number=3,
            chunk_cfg={"strategy": "file"},
            entries=[
                ManifestEntry(path="data.csv", content_hash="aa" * 32, weight=1.0),
                ManifestEntry(path="meta.json", content_hash="bb" * 32, weight=0.5),
            ],
        )
        d1 = compute_manifest_digest(manifest)
        d2 = compute_manifest_digest(manifest)
        assert d1 == d2

    def test_digest_stable_across_instances(self) -> None:
        """Two manifest instances with identical data produce the same digest."""
        entries = [
            ManifestEntry(path="x.bin", content_hash="aa" * 32),
            ManifestEntry(path="y.bin", content_hash="bb" * 32),
        ]
        m1 = Manifest(corpus_slug="stable", version_number=2, entries=entries)
        m2 = Manifest(corpus_slug="stable", version_number=2, entries=entries)

        assert compute_manifest_digest(m1) == compute_manifest_digest(m2)

    def test_no_randomness_in_digest(self) -> None:
        """Digest is purely a function of manifest content; no random salt."""
        manifest = Manifest(
            corpus_slug="no-randomness",
            version_number=1,
            entries=[ManifestEntry(path="f.txt", content_hash="aa" * 32)],
        )
        # Call many times in a row — all must match.
        digests = {compute_manifest_digest(manifest) for _ in range(50)}
        assert len(digests) == 1
