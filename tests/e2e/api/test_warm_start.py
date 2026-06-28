# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""E2E tests for warm-start API validation (spec 039).

Covers the ``base_model_ref`` validation path on ``POST /v1/training/start``.
The validation runs synchronously before any DB sequence access, so these
tests are deterministic without a trained model on disk.
"""

from __future__ import annotations

import pytest

BASE_CONFIG = {
    "n_layer": 1,
    "n_embd": 16,
    "n_head": 4,
    "block_size": 16,
    "num_steps": 1,
    "learning_rate": 0.01,
    "compute_backend": "auto",
}


@pytest.mark.asyncio
async def test_warm_start_nonexistent_base_ref_returns_422(client):
    """A ``base_model_ref`` pointing to a missing checkpoint returns 422."""
    payload = {**BASE_CONFIG, "base_model_ref": 99999}
    r = await client.post("/v1/training/start", json=payload)
    assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text}"


def test_base_model_ref_is_a_known_field():
    """``base_model_ref`` exists on ``TrainConfig`` (not rejected by extra=forbid).

    ``TrainConfig`` uses ``ConfigDict(extra="forbid")``; an unknown field would
    raise a ``ValidationError``. This confirms the field was added (T014) and
    accepts an integer experiment ID with ``None`` default (FR-001).
    """
    from anvil.api.v1.training import TrainConfig

    cfg = TrainConfig(**BASE_CONFIG)
    assert cfg.base_model_ref is None

    cfg_with_ref = TrainConfig(**{**BASE_CONFIG, "base_model_ref": 7})
    assert cfg_with_ref.base_model_ref == 7
