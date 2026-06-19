"""Bootstrap result data class — outcome of a demo data bootstrap operation.

Provides the ``BootstrapResult`` Pydantic model used by
``DemoBootstrapService`` to report the result of importing bundled
demo data into the database.
"""

from pydantic import BaseModel, Field


class BootstrapResult(BaseModel):
    """Outcome of a ``bootstrap_all()`` run."""

    corpora_created: int = 0
    datasets_created: int = 0
    corpora_skipped: int = 0
    datasets_skipped: int = 0
    errors: list[str] = Field(default_factory=list)
    total_time_ms: float = 0.0
