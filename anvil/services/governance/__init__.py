# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Governance domain — sample data provenance, audit, and acceptable-use gate.

This domain sub-package implements the lawful/ethical/auditable governance
layer for the anvil workbench. It is organized as a single bounded context
(Constitution Article X) with one-class-per-file (ADR-020) and Pydantic
BaseModel result/value types (ADR-019).

Modules
-------
audit_service
    Hash-chained, tamper-evident audit trail service.
governance_service
    Acceptable-use gate, license catalog, and provenance assignment.
license_seed
    Seed data for the approved-license catalog (broad OSI/CC set).
data_origin
    StrEnum: ``BUNDLED`` (bundled sample data) / ``USER`` (user-supplied).
audit_action
    StrEnum: types of audit lifecycle events.
audit_target_type
    StrEnum: types of entities that can be audit targets.
audit_outcome
    StrEnum: outcomes of audited actions (success/rejected/error).
gate_decision
    Pydantic result type for acceptable-use gate evaluations.
chain_verify_result
    Pydantic result type for audit chain integrity verification.
provenance_view
    Pydantic result type surfacing a dataset/corpus provenance record.
"""
