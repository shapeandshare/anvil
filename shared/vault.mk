# Vault health tooling — mechanical audit + graph health analysis
#
# Requires PyYAML (already in project deps). Graph health requires
# networkx (optional — skipped if not installed).
#
# See docs/vault/Systems/Vault Health.md.

VAULT_DIR := docs/vault

.PHONY: vault-audit
vault-audit: $(VENV_DIR)/activate ## Run vault audit + graph health (report only, no changes)
	$(PYTHON) scripts/ci/vault_audit.py $(VAULT_DIR)

.PHONY: vault-audit-apply
vault-audit-apply: $(VENV_DIR)/activate ## Run vault audit with safe auto-fixes applied in-place
	$(PYTHON) scripts/ci/vault_audit.py $(VAULT_DIR) --apply

.PHONY: vault-audit-diff
vault-audit-diff: $(VENV_DIR)/activate ## Show auto-fixes the audit would apply (no changes)
	$(PYTHON) scripts/ci/vault_audit.py $(VAULT_DIR) --diff

.PHONY: vault-audit-fast
vault-audit-fast: $(VENV_DIR)/activate ## Mechanical audit only (skip networkx graph-health pass)
	$(PYTHON) scripts/ci/vault_audit.py $(VAULT_DIR) --skip-graph-health