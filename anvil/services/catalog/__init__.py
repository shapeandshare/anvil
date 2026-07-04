"""Model catalog domain.

Provides the ``ModelCatalogService`` that uses the MLflow Model Registry as
the single source of truth for all model identity, versions, and metadata,
value objects (``ModelRef``, ``CatalogEntry``), and types (``CatalogKind``,
``LifecycleState``). The catalog replaces the legacy ``ExternalModel``-based
dual-track system — all models (trained, external/imported, merged) live in
one registry.
"""