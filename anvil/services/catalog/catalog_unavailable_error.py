# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Catalog unavailability error (fail-closed contract)."""


class CatalogUnavailableError(RuntimeError):
    """Raised when the MLflow Model Registry backend is unreachable
    or in a permanent failure state.

    Unlike :class:`anvil.services.tracking.TrackingService` which
    returns empty results in degraded mode, the catalog fails closed
    (FR-009). This error is translated by the FastAPI exception handler
    to a ``503 CATALOG_UNAVAILABLE`` response.
    """