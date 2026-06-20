"""File metadata model for storage backends."""

from datetime import datetime

from pydantic import BaseModel


class FileInfo(BaseModel):
    """Metadata descriptor for a single stored file.

    Represents a file tracked by a :class:`FileStore` backend, carrying
    identity, size, content-type, and timestamp information. Instances are
    typically produced by :meth:`FileStore.list` and consumed by service
    and API layers for display, filtering, or cache-invalidation logic.
    """

    path: str
    size: int
    etag: str
    content_type: str
    created_at: datetime
    updated_at: datetime
