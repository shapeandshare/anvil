# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Server health check operations.

Provides ``HealthGetCommand`` for server liveness (``GET /v1/health``) and
``HealthDetailedCommand`` for system metrics (``GET /v1/health/detailed``),
aggregated via ``HealthClient``.
"""