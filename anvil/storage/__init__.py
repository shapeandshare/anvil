"""File storage abstraction.

``anvil.storage`` defines an abstract ``FileStore`` interface and
provides a ``LocalFileStore`` implementation backed by the local
filesystem. Designed to be extensible to S3-compatible or other
remote backends.
"""
