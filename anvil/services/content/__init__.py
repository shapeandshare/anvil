# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Content repository — versioned, reproducible training data.

``anvil.services.content`` is the domain sub-package (Article X) for the
versioned Content Repository (feature 016). It provides a versioned,
reproducible content substrate with immutable version pinning, concurrent
isolated ingestion, automated validation gates, weighted composition, and
lineage tracking.

Local mode uses a pure-Python, content-addressed implementation over the
existing ``LocalFileStore`` + SQLite metadata (no external service). SaaS
mode (future) uses a LakeFS-backed implementation behind the same
``VersionedContentStore`` interface.

See ADR-033 and ``docs/vault/Specs/019 LakeFS Content Repo/`` for the full architecture.
"""
