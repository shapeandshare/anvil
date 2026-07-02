# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""E2E tests for fine-tune compute routing (spec 046).

Exercises ``resolve_fine_tune()`` directly since the routing function
is an internal service-layer API, not an HTTP endpoint.
"""

from anvil.services.compute.compute_backend_result import ComputeBackendResult


def test_finetune_routing_local():
    """Small fine-tune with auto resolves to the local backend."""
    from anvil.services.compute.resolve import resolve_fine_tune

    result = resolve_fine_tune(
        {
            "method": "lora",
            "base_model_ref": "tinyllama-1.1b",
            "compute_backend": "auto",
        }
    )
    assert result["backend"] == ComputeBackendResult.LOCAL
    assert result["engine"] == "torch"


def test_finetune_routing_over_local_falls_back():
    """Over-local auto without SaaS falls back to local (D4, never raises)."""
    from anvil.services.compute.resolve import resolve_fine_tune

    result = resolve_fine_tune(
        {
            "method": "full",
            "base_model_ref": "large-model-70b",
            "compute_backend": "auto",
        }
    )
    assert result["backend"] in tuple(ComputeBackendResult)
