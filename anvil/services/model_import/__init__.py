"""Model import domain.

Provides the ``ModelSource`` abstraction for resolving metadata from external
model registries (HuggingFace Hub, local filesystem), the ``ModelImportService``
for async job-based import orchestration, and concrete ``ModelSource``
implementations.
"""