# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Log reader abstraction for service and job log streams.

Local mode reads disk files; SaaS mode reads CloudWatch Logs
via boto3. Graceful degradation to NullLogsReader when the
[monitoring] extra is not installed.
"""

from abc import ABC, abstractmethod


class LogsReader(ABC):
    """Abstract reader for service and job log streams."""

    @abstractmethod
    async def read_service_logs(
        self, service_name: str, lines: int = 100
    ) -> list[dict]:
        """Read recent log lines for a named service.

        Parameters
        ----------
        service_name : str
            Service identifier (e.g., ``"anvil-web"``, ``"anvil-mlflow"``).
        lines : int
            Maximum number of log lines to return. Defaults to 100.

        Returns
        -------
        list[dict]
            List of log entries, each with ``timestamp``, ``message``,
            and optionally ``level`` / ``trace_id``.
        """

    @abstractmethod
    async def read_job_logs(
        self, job_id: int, batch_log_stream: str, lines: int = 100
    ) -> list[dict]:
        """Read log lines for a terminated compute pod.

        Parameters
        ----------
        job_id : int
            Training job ID.
        batch_log_stream : str
            CloudWatch Logs stream name for the compute pod.
        lines : int
            Maximum number of log lines to return. Defaults to 100.

        Returns
        -------
        list[dict]
            List of log entries, each with ``timestamp`` and ``message``.
        """


class LocalLogsReader(LogsReader):
    """File-based log reader for local mode.

    Reads from ``data/logs/{service_name}.log`` for service logs
    and ``data/logs/jobs/{job_id}.log`` for job logs.
    """

    async def read_service_logs(
        self, service_name: str, lines: int = 100
    ) -> list[dict]:
        """Read recent service logs from the local filesystem."""

    async def read_job_logs(
        self, job_id: int, batch_log_stream: str, lines: int = 100
    ) -> list[dict]:
        """Read compute pod logs from the local filesystem."""


class CloudWatchLogsReader(LogsReader):
    """CloudWatch Logs-based reader for SaaS mode.

    Uses ``boto3 logs filter-log-events`` for ECS service
    log groups and Batch compute pod log streams.
    """

    def __init__(self, log_group_map: dict[str, str]) -> None: ...

    async def read_service_logs(
        self, service_name: str, lines: int = 100
    ) -> list[dict]:
        """Read service logs from CloudWatch Logs."""

    async def read_job_logs(
        self, job_id: int, batch_log_stream: str, lines: int = 100
    ) -> list[dict]:
        """Read compute pod logs from CloudWatch Logs."""


class NullLogsReader(LogsReader):
    """Null reader returned when [monitoring] extra is not installed.

    Returns a structured ``{"status": "not_configured"}`` response
    rather than raising ``ImportError``.
    """

    async def read_service_logs(
        self, service_name: str, lines: int = 100
    ) -> list[dict]:
        """Return a 'not configured' response for service logs."""
        return [
            {
                "status": "not_configured",
                "message": "Log viewer requires the anvil[monitoring] extra",
            }
        ]

    async def read_job_logs(
        self, job_id: int, batch_log_stream: str, lines: int = 100
    ) -> list[dict]:
        """Return a 'not configured' response for job logs."""
        return [
            {
                "status": "not_configured",
                "message": "Log viewer requires the anvil[monitoring] extra",
            }
        ]


# Implementations:
# - LocalLogsReader: pathlib.Path (shared, in anvil/storage/logs.py)
# - CloudWatchLogsReader: boto3 logs client (new, in anvil/_saas/implementations/cw_logs_reader.py)
