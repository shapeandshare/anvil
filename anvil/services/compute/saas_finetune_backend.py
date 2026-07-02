# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""SaaS fine-tune compute backend.

Wraps a :class:`SaasFinetuneProvider` transport via submit-then-poll
pattern (spec 047).  The provider seam is test-injectable; in production
a real transport (AWS Batch, etc.) will implement
:class:`SaasFinetuneProvider`.

Auto-registers at module import time via :func:`register()`.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from .compute_backend_result import ComputeBackendResult
from .compute_status import ComputeStatus
from .protocol import ProgressCallback, StopCheck
from .registry import register
from .registry_backend import RegistryBackend
from .result import ComputeResult
from .training_engine import TrainingEngine

logger = logging.getLogger(__name__)


#: Maximum number of retries for transient provider failures.
MAX_RETRIES: int = 3

#: Backoff delays (seconds) between retry attempts.
RETRY_BACKOFFS: list[int] = [30, 90, 270]


def _saas_configured() -> bool:
    """Check whether the SaaS fine-tune backend is configured.

    Returns ``True`` if the ``ANVIL_SAAS_ENDPOINT`` environment variable
    is set to a non-empty value.

    Returns
    -------
    bool
        ``True`` if the SaaS endpoint is configured.
    """
    return bool(os.environ.get("ANVIL_SAAS_ENDPOINT"))


class SaasFinetuneBackend:
    """Compute backend that routes fine-tuning to a SaaS provider.

    Follows the submit-then-poll pattern established by
    :class:`ModalBackend`: submits a job via ``provider.submit()``,
    polls via ``provider.poll_status()``, and fetches the resulting
    adapter via ``provider.fetch_adapter()`` upon completion.
    """

    name = RegistryBackend.SAAS_FINETUNE

    def __init__(self, provider: Any | None = None) -> None:
        """Initialise the SaaS fine-tune backend.

        Parameters
        ----------
        provider : SaasFinetuneProvider | None, optional
            Injected transport provider.  When ``None``, :meth:`run`
            will fail at call time (production MVP: the real transport
            is not yet implemented).
        """
        self._provider = provider

    @staticmethod
    def is_available() -> bool:
        """Check whether the SaaS fine-tune backend is available.

        Delegates to the module-level :func:`_saas_configured` function,
        which checks the ``ANVIL_SAAS_ENDPOINT`` environment variable.

        Returns
        -------
        bool
            ``True`` if the SaaS endpoint is configured.
        """
        return _saas_configured()

    async def run(
        self,
        docs: list[str],
        config: dict[str, Any],
        *,
        progress_callback: ProgressCallback,
        stop_check: StopCheck,
    ) -> ComputeResult:
        """Submit and monitor a fine-tuning job on the SaaS provider.

        Parameters
        ----------
        docs : list[str]
            Training documents (raw text strings).
        config : dict[str, Any]
            Hyperparameter dictionary forwarded to the SaaS provider.
        progress_callback : ProgressCallback
            Callable invoked with ``(-1, 0.0)`` on submission to signal
            that the job was submitted remotely.
        stop_check : StopCheck
            Callable returning ``True`` if the user has requested
            cancellation; triggers a failed result with an error.

        Returns
        -------
        ComputeResult
            Completed result with ``adapter_id`` and ``adapter_path``
            artifact URI, or failed result with an error message.
        """
        provider = self._provider
        if provider is None:
            return ComputeResult(
                status=ComputeStatus.FAILED,
                error_message="No SaaS provider configured",
                backend=ComputeBackendResult.SAAS,
                engine=TrainingEngine.TORCH,
            )

        job_ref: str
        try:
            job_ref = await provider.submit(config)
        except Exception as exc:
            logger.warning("SaaS provider submit failed: %s", exc)
            return ComputeResult(
                status=ComputeStatus.FAILED,
                error_message=f"Failed to submit job: {exc}",
                backend=ComputeBackendResult.SAAS,
                engine=TrainingEngine.TORCH,
            )

        if progress_callback is not None:
            progress_callback(-1, 0.0)

        for attempt in range(MAX_RETRIES + 1):
            while True:
                if stop_check():
                    return ComputeResult(
                        status=ComputeStatus.FAILED,
                        error_message="Training cancelled by user",
                        backend=ComputeBackendResult.SAAS,
                        engine=TrainingEngine.TORCH,
                    )

                try:
                    status: ComputeStatus = await provider.poll_status(job_ref)
                except Exception as exc:
                    if attempt < MAX_RETRIES:
                        backoff = RETRY_BACKOFFS[attempt]
                        logger.warning(
                            "Poll failed (attempt %d/%d), retrying in %ds: %s",
                            attempt + 1,
                            MAX_RETRIES,
                            backoff,
                            exc,
                        )
                        await asyncio.sleep(backoff)
                        break  # outer loop retries
                    return ComputeResult(
                        status=ComputeStatus.FAILED,
                        error_message=f"Poll failed after {MAX_RETRIES} retries: {exc}",
                        backend=ComputeBackendResult.SAAS,
                        engine=TrainingEngine.TORCH,
                    )

                if status == ComputeStatus.COMPLETED:
                    try:
                        adapter_path: str = await provider.fetch_adapter(job_ref)
                    except Exception as exc:
                        return ComputeResult(
                            status=ComputeStatus.FAILED,
                            error_message=f"Failed to fetch adapter: {exc}",
                            backend=ComputeBackendResult.SAAS,
                            engine=TrainingEngine.TORCH,
                        )
                    return ComputeResult(
                        status=ComputeStatus.COMPLETED,
                        adapter_id=job_ref,
                        artifact_uris={"adapter_path": adapter_path},
                        backend=ComputeBackendResult.SAAS,
                        engine=TrainingEngine.TORCH,
                        exported_remotely=True,
                    )

                if status == ComputeStatus.FAILED:
                    return ComputeResult(
                        status=ComputeStatus.FAILED,
                        backend=ComputeBackendResult.SAAS,
                        engine=TrainingEngine.TORCH,
                    )

                await asyncio.sleep(2)

        # -- unreachable: all paths return inside the loop --
        return ComputeResult(  # pragma: no cover
            status=ComputeStatus.FAILED,
            error_message="Unexpected: poll loop exhausted without result",
            backend=ComputeBackendResult.SAAS,
            engine=TrainingEngine.TORCH,
        )


def _saas_finetune_factory() -> SaasFinetuneBackend:
    """Factory callable for the SaaS fine-tune backend.

    Returns
    -------
    SaasFinetuneBackend
        A new instance of the SaaS fine-tune compute backend.
    """
    return SaasFinetuneBackend()


register(RegistryBackend.SAAS_FINETUNE, _saas_finetune_factory)  # type: ignore[arg-type]