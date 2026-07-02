# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Protocol for a SaaS fine-tune provider transport.

Defines the structural typing contract (PEP 544) for injecting a test-
friendly transport abstraction behind :class:`SaasFinetuneBackend`.  The
provider seam follows the same pattern as :class:`ModalBackend`'s
``function_factory`` parameter.

The protocol has exactly three methods --- no ``ResourceSpec``, no tenant
fields, no event-stream types (YAGNI, Article XI).
"""

from __future__ import annotations

from typing import Any, Protocol

from .compute_status import ComputeStatus


class SaasFinetuneProvider(Protocol):
    """Structural contract for a SaaS fine-tune provider transport.

    Any class with ``submit``, ``poll_status``, and ``fetch_adapter``
    async methods satisfies this protocol.  No inheritance required.

    The protocol exists solely to decouple backend orchestration from
    transport implementation.  In tests a fake is injected; in production
    a real transport (AWS Batch, etc.) implements this protocol.
    """

    async def submit(self, config: dict[str, Any]) -> str:
        """Submit a fine-tuning job and return an opaque job reference.

        Parameters
        ----------
        config : dict[str, Any]
            Training configuration (method, hyperparameters, model ref).

        Returns
        -------
        str
            Opaque job reference for subsequent :meth:`poll_status` and
            :meth:`fetch_adapter` calls.
        """

    async def poll_status(self, job_ref: str) -> ComputeStatus:
        """Poll the current status of a previously submitted job.

        Parameters
        ----------
        job_ref : str
            Opaque job reference returned by :meth:`submit`.

        Returns
        -------
        ComputeStatus
            Current lifecycle status of the remote job.
        """

    async def fetch_adapter(self, job_ref: str) -> str:
        """Fetch a completed job's adapter artifact to a local path.

        Parameters
        ----------
        job_ref : str
            Opaque job reference returned by :meth:`submit`.

        Returns
        -------
        str
            Local filesystem path where the adapter artifact was
            downloaded.
        """