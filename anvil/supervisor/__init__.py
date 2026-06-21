# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Background process manager.

``anvil.supervisor`` manages the lifecycle of background services
(MLflow tracking server, web server process) — starting, stopping,
health-checking, and streaming log output for operations dashboard
consumption.
"""
