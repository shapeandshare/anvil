"""Vault health services — mechanical audit, graph health, and CI validators.

This domain sub-package provides vault analysis tools previously maintained
as standalone CI scripts under ``scripts/ci/``. It includes vault frontmatter
and wikilink auditing, graph-theoretic health analysis (connectivity,
topology, hygiene, temporal decay, structural gaps), link prediction, and
CI gate validators (ADR uniqueness, guarded import discipline, bump scope).

Clients interact through the ``anvil-vault`` CLI or by importing service
classes directly:

.. code-block:: python

    from anvil.services.vault import VaultHealthService, GraphHealthService

    svc = VaultHealthService(vault_dir="docs/vault")
    report = await svc.run_audit()
"""
