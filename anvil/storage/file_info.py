"""File metadata model for storage backends."""

from pydantic import BaseModel


class FileInfo(BaseModel):
    """Metadata descriptor for a single stored file.

    Represents a file tracked by a :class:`FileStore` backend, carrying
    identity, size, content-type, and timestamp information. Instances are
    typically produced by :meth:`FileStore.list` and consumed by service
    and API layers for display, filtering, or cache-invalidation logic.

    Parameters
    ----------
    path : str
        Relative or logical path of the file within the storage backend.
    size : int
        File size in bytes.
    etag : str
        Entity tag for change detection (e.g. nanosecond mtime string).
    content_type : str
        MIME type of the file content.
    created_at : datetime
        Timestamp of file creation.
    updated_at : datetime
        Timestamp of last file modification.
    """
