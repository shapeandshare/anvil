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

# ── Constitution mechanical checks ────────────────────────────────────

CONSTITUTION_CHECKS = check-init-py check-relative-imports check-one-class check-import-placement check-nesting check-py-typed check-core-deps check-layers

.PHONY: constitution-check $(CONSTITUTION_CHECKS)

constitution-check: $(CONSTITUTION_CHECKS) ## Run all constitution mechanical checks
	@echo "All constitution checks passed."

check-init-py: $(VENV_DIR)/activate ## Verify __init__.py ownership policy
	$(VENV_BIN)/anvil-vault check-init-py

check-relative-imports: $(VENV_DIR)/activate ## Verify no absolute anvil. imports
	$(VENV_BIN)/anvil-vault check-relative-imports

check-one-class: $(VENV_DIR)/activate ## Verify one class per file
	$(VENV_BIN)/anvil-vault check-one-class

check-import-placement: $(VENV_DIR)/activate ## Verify imports at top of file
	$(VENV_BIN)/anvil-vault check-import-placement

check-nesting: $(VENV_DIR)/activate ## Verify max 2 levels package nesting
	$(VENV_BIN)/anvil-vault check-nesting

check-py-typed: $(VENV_DIR)/activate ## Verify py.typed marker exists and is configured
	$(VENV_BIN)/anvil-vault check-py-typed

check-core-deps: $(VENV_DIR)/activate ## Verify anvil/core/ has zero third-party deps
	$(VENV_BIN)/anvil-vault check-core-deps

check-layers: $(VENV_DIR)/activate ## Verify layer boundaries in architecture
	$(VENV_BIN)/anvil-vault check-layers