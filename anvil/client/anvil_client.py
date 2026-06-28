# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Top-level async facade for the anvil server API.

``AnvilClient`` is the sole public entry point for SDK consumers.
It aggregates per-domain sub-clients over a single shared ``Transport``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from ._shared.server_config import ServerConfig
from ._shared.transport import Transport

if TYPE_CHECKING:
    from .compute.compute_client import ComputeClient
    from .content.content_client import ContentClient
    from .corpora.corpora_client import CorporaClient
    from .datasets.datasets_client import DatasetsClient
    from .eval.eval_client import EvalClient
    from .experiments.experiments_client import ExperimentsClient
    from .governance.governance_client import GovernanceClient
    from .health.health_client import HealthClient
    from .inference.inference_client import InferenceClient
    from .models.models_client import ModelsClient
    from .registry.registry_client import RegistryClient
    from .services.services_client import ServicesClient
    from .training.training_client import TrainingClient

from .compute.compute_client import ComputeClient
from .content.content_client import ContentClient
from .corpora.corpora_client import CorporaClient
from .datasets.datasets_client import DatasetsClient
from .eval.eval_client import EvalClient
from .experiments.experiments_client import ExperimentsClient
from .governance.governance_client import GovernanceClient
from .health.health_client import HealthClient
from .inference.inference_client import InferenceClient
from .models.models_client import ModelsClient
from .registry.registry_client import RegistryClient
from .services.services_client import ServicesClient
from .training.training_client import TrainingClient


class AnvilClient:
    """Top-level async facade for the anvil server API.

    Aggregates per-domain sub-clients over a single shared ``Transport``.
    The only public entry point for SDK consumers.

    Parameters
    ----------
    base_url : str | None, optional
        Base URL of the anvil server. Falls back to ``ServerConfig.from_env()``.
    api_key : str | None, optional
        API key for authenticated requests.
    timeout : float | None, optional
        Request timeout in seconds.
    retry_count : int | None, optional
        Maximum number of retry attempts for failed requests.
    config : ServerConfig | None, optional
        Pre-built ``ServerConfig``. If provided, overrides all other
        connection parameters.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float | None = None,
        retry_count: int | None = None,
        config: ServerConfig | None = None,
        _client: httpx.AsyncClient | None = None,
    ) -> None:
        if config is not None:
            resolved = config
        else:
            resolved = ServerConfig.from_env(
                base_url=base_url,
                timeout=timeout,
                retry_count=retry_count,
            )
        self._config: ServerConfig = resolved
        self._transport = Transport(self._config, api_key, client=_client)
        self._health: HealthClient | None = None
        self._datasets: DatasetsClient | None = None
        self._experiments: ExperimentsClient | None = None
        self._inference: InferenceClient | None = None
        self._registry: RegistryClient | None = None
        self._training: TrainingClient | None = None
        self._corpora: CorporaClient | None = None
        self._eval: EvalClient | None = None
        self._compute: ComputeClient | None = None
        self._services: ServicesClient | None = None
        self._governance: GovernanceClient | None = None
        self._content: ContentClient | None = None
        self._models: ModelsClient | None = None

    # -- config readback (US-1 acceptance) ------------------------------------

    @property
    def config(self) -> ServerConfig:
        """Return the resolved server configuration.

        Returns
        -------
        ServerConfig
            The configuration object with base URL, timeout,
            and retry settings.
        """
        return self._config

    # -- domain sub-client properties -----------------------------------------

    @property
    def health(self) -> HealthClient:
        """Access server health check operations.

        Lazily creates the ``HealthClient`` on first access.

        Returns
        -------
        HealthClient
            Domain client for server health operations.
        """
        if self._health is None:
            self._health = HealthClient(self._transport)
        return self._health

    @property
    def datasets(self) -> DatasetsClient:
        """Access dataset lifecycle operations.

        Lazily creates the ``DatasetsClient`` on first access.

        Returns
        -------
        DatasetsClient
            Domain client for dataset operations.
        """
        if self._datasets is None:
            self._datasets = DatasetsClient(self._transport)
        return self._datasets

    @property
    def training(self) -> TrainingClient:
        """Access training orchestration operations.

        Lazily creates the ``TrainingClient`` on first access.

        Returns
        -------
        TrainingClient
            Domain client for training (start, stop, status, SSE stream).
        """
        if self._training is None:
            self._training = TrainingClient(self._transport)
        return self._training

    @property
    def experiments(self) -> ExperimentsClient:
        """Access experiment operations.

        Lazily creates the ``ExperimentsClient`` on first access.

        Returns
        -------
        ExperimentsClient
        """
        if self._experiments is None:
            self._experiments = ExperimentsClient(self._transport)
        return self._experiments

    @property
    def inference(self) -> InferenceClient:
        """Access model inference operations.

        Lazily creates the ``InferenceClient`` on first access.

        Returns
        -------
        InferenceClient
            Domain client for listing models and sampling text.
        """
        if self._inference is None:
            self._inference = InferenceClient(self._transport)
        return self._inference

    @property
    def registry(self) -> RegistryClient:
        """Access model registry operations.

        Lazily creates the ``RegistryClient`` on first access.

        Returns
        -------
        RegistryClient
        """
        if self._registry is None:
            self._registry = RegistryClient(self._transport)
        return self._registry

    @property
    def corpora(self) -> CorporaClient:
        """Access corpus management operations.

        Returns
        -------
        CorporaClient
        """
        if self._corpora is None:
            self._corpora = CorporaClient(self._transport)
        return self._corpora

    @property
    def eval(self) -> EvalClient:
        """Access model evaluation and eval dataset operations.

        Returns
        -------
        EvalClient
        """
        if self._eval is None:
            self._eval = EvalClient(self._transport)
        return self._eval

    @property
    def compute(self) -> ComputeClient:
        """Access compute backend operations.

        Returns
        -------
        ComputeClient
        """
        if self._compute is None:
            self._compute = ComputeClient(self._transport)
        return self._compute

    @property
    def services(self) -> ServicesClient:
        """Access service lifecycle operations.

        Returns
        -------
        ServicesClient
        """
        if self._services is None:
            self._services = ServicesClient(self._transport)
        return self._services

    @property
    def governance(self) -> GovernanceClient:
        """Access governance and audit operations.

        Returns
        -------
        GovernanceClient
        """
        if self._governance is None:
            self._governance = GovernanceClient(self._transport)
        return self._governance

    @property
    def content(self) -> ContentClient:
        """Access versioned content repository operations.

        Returns
        -------
        ContentClient
        """
        if self._content is None:
            self._content = ContentClient(self._transport)
        return self._content

    @property
    def models(self) -> ModelsClient:
        """Access external model import and registry operations.

        Returns
        -------
        ModelsClient
        """
        if self._models is None:
            self._models = ModelsClient(self._transport)
        return self._models

    # -- auth (US5) -----------------------------------------------------------

    async def login(self, api_key: str) -> None:
        """Authenticate with an API key via session login.

        Performs ``POST /login`` with the given API key. On success the
        server sets a session cookie, which the transport's ``httpx``
        client jar stores automatically for subsequent requests.

        Parameters
        ----------
        api_key : str
            API key to authenticate with.
        """
        await self._transport.request(
            "POST",
            "/login",
            json={"api_key": api_key},
            response_model=dict,  # type: ignore[arg-type]
        )
        self._transport._auth_mode = "session"

    async def logout(self) -> None:
        """End the current authenticated session.

        Performs ``POST /logout`` to clear the session cookie on the
        server side, then resets the transport auth mode to ``"none"``.
        """
        await self._transport.request(
            "POST",
            "/logout",
            response_model=dict,  # type: ignore[arg-type]
        )
        self._transport._auth_mode = "none"

    # -- lifecycle ------------------------------------------------------------

    async def aclose(self) -> None:
        """Close the underlying transport and release resources.

        Idempotent — safe to call multiple times.
        """
        await self._transport.aclose()

    async def __aenter__(self) -> AnvilClient:
        """Enter async context manager.

        Returns
        -------
        AnvilClient
            The client instance.
        """
        return self

    async def __aexit__(self, *exc: object) -> None:
        """Exit async context manager and close the transport."""
        await self.aclose()
