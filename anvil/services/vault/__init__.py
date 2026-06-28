# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Vault health services — mechanical audit, graph health, constitution checks, and CI validators.

This domain sub-package provides vault analysis tools previously maintained
as standalone CI scripts under ``scripts/ci/``. It includes vault frontmatter
and wikilink auditing, graph-theoretic health analysis (connectivity,
topology, hygiene, temporal decay, structural gaps), link prediction,
constitution mechanical checks (init-py ownership, relative imports, one-class-per-file,
import placement, nesting depth, py.typed, core deps, layer boundaries), and
CI gate validators (ADR uniqueness, guarded import discipline, bump scope).

Clients interact through the ``anvil-vault`` CLI or by importing service
classes directly:

.. code-block:: python

    from anvil.services.vault import VaultHealthService, GraphHealthService

    svc = VaultHealthService(vault_dir="docs/vault")
    report = await svc.run_audit()
"""
