# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""HTTP client SDK for the anvil server API.

Provides ``AnvilClient`` — an async, typed, fully-typed facade over the anvil
REST API and SSE streaming endpoints. Domain operations are organized under
named sub-clients (``client.datasets.*``, ``client.training.*``, etc.).

Sub-packages
------------
_shared
    Cross-domain infrastructure: transport, config, envelope, errors,
    base command, SSE event types.
health
    Server health check operations.
datasets
    Dataset lifecycle (CRUD, upload, export, search).
training
    Training orchestration (start, stop, status, SSE stream).
experiments
    Experiment listing, comparison, metrics, artifact download.
registry
    Model registry (register, list, get, delete).
inference
    Model inference (list models, sample text).
corpora
    Corpus management (CRUD, ingest, files, path analysis).
eval
    Model evaluation (perplexity) and eval dataset management.
compute
    Compute backend enumeration.
services
    Service lifecycle (list, logs, start, stop, restart).
governance
    Audit trail, license catalog, dataset provenance, takedown.
content
    Versioned content repository (corpora, ingestion sessions, locks).
"""