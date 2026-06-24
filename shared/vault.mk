# Vault health tooling — mechanical audit + graph health analysis
#
# Delegates to the ``anvil-vault`` CLI. Legacy ``scripts/ci/`` thin wrappers
# have been removed; all logic lives in the package.
#
# See docs/vault/Systems/Vault Health.md.

VAULT_DIR := docs/vault

.PHONY: vault-audit
vault-audit: $(VENV_DIR)/activate ## Run vault audit + graph health (report only, no changes)
	$(VENV_BIN)/anvil-vault audit --vault-dir $(VAULT_DIR)

.PHONY: vault-audit-apply
vault-audit-apply: $(VENV_DIR)/activate ## Run vault audit with safe auto-fixes applied in-place
	$(VENV_BIN)/anvil-vault audit --vault-dir $(VAULT_DIR) --apply

.PHONY: vault-audit-diff
vault-audit-diff: $(VENV_DIR)/activate ## Show auto-fixes the audit would apply (no changes)
	$(VENV_BIN)/anvil-vault audit --vault-dir $(VAULT_DIR) --diff

.PHONY: vault-audit-fast
vault-audit-fast: $(VENV_DIR)/activate ## Mechanical audit only (skip networkx graph-health pass)
	$(VENV_BIN)/anvil-vault audit --vault-dir $(VAULT_DIR) --skip-graph-health

.PHONY: adr-check
adr-check: ## Validate ADR uniqueness and naming conventions
	$(VENV_BIN)/anvil-vault check-adrs

.PHONY: guarded-imports-check
guarded-imports-check: ## Validate TYPE_CHECKING guarded imports are annotation-only
	$(VENV_BIN)/anvil-vault check-guarded-imports