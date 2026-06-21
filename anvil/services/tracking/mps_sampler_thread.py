# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""MPS sampler thread — background thread for periodic MPS metric sampling.

Provides the ``MPSSamplerThread`` class that periodically queries Apple
Silicon GPU metrics and logs them to MLflow during training runs.
"""

import asyncio
import threading

from .mps_metrics_collector import MPSMetricsCollector
from .tracking import TrackingService


class MPSSamplerThread(threading.Thread):
    """Background thread that periodically samples MPS metrics into MLflow.

    Runs in a daemon thread during training to log GPU utilisation and
    memory usage as ``system/gpu_util_pct`` and ``system/gpu_memory_gb``
    metrics to the active MLflow run.
    """

    def __init__(
        self,
        tracking_svc: TrackingService,
        run_id: str,
        interval: float = 5.0,
    ):
        """Initialise the sampler thread.

        Parameters
        ----------
        tracking_svc : TrackingService
            The tracking service for logging metrics.
        run_id : str
            The MLflow run ID to log metrics to.
        interval : float
            Sampling interval in seconds. Defaults to ``5.0``.
        """
        super().__init__(daemon=True, name="mps-metrics-sampler")
        self._tracking_svc = tracking_svc
        self._run_id = run_id
        self._interval = interval
        self._stop_event = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None

    def run(self) -> None:
        """Run the sampling loop until stopped.

        Queries MPS metrics at the configured interval and logs them
        to the MLflow run using an asyncio event loop running in this
        thread.
        """
        try:
            self._loop = asyncio.new_event_loop()
            step = 0
            while not self._stop_event.wait(self._interval):
                util = MPSMetricsCollector.get_utilization()
                mem = MPSMetricsCollector.get_memory_gb()
                if util is not None:
                    self._loop.run_until_complete(
                        self._tracking_svc.log_metric(
                            self._run_id, "system/gpu_util_pct", util, step=step
                        )
                    )
                if mem is not None:
                    self._loop.run_until_complete(
                        self._tracking_svc.log_metric(
                            self._run_id, "system/gpu_memory_gb", mem, step=step
                        )
                    )
                step += 1
        except Exception:
            pass
        finally:
            if self._loop:
                self._loop.close()

    def stop(self) -> None:
        """Signal the sampler thread to stop.

        Sets the internal stop event, causing the next iteration of
        the sampling loop to exit.
        """
        self._stop_event.set()
