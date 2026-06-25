# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""API key generation, persistence, and validation.

Generates a cryptographically secure API key on first startup,
persists it to a ``0600``-permission state file so the key
survives restarts, and provides constant-time validation via
:func:`secrets.compare_digest`.

The key is NEVER written to log files or printed in full to the
console.  On first generation only a short prefix hint (first 8
characters) is emitted to stderr.  The full key is retrievable
via ``anvil --show-api-key`` (CLI command).

If the ``ANVIL_API_KEY`` environment variable is set, it is read
once at startup and then removed from ``os.environ`` to limit
``/proc/<pid>/environ`` exposure (FR-026).
"""

import logging
import os
import secrets
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_API_KEY_FILE = Path("data/.api_key")
"""Path: Default location for the persisted API key file."""


class ApiKeyStore:
    """Manages the API key lifecycle — generation, persistence, retrieval, and
    constant-time validation.

    Parameters
    ----------
    key_path : str or Path, optional
        Path to the API key state file.  Defaults to ``data/.api_key``.
    """

    def __init__(self, key_path: str | Path | None = None) -> None:
        self._key_path = Path(key_path) if key_path else _API_KEY_FILE
        self._key: str | None = None
        self._load_or_generate()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def verify(self, key: str) -> bool:
        """Constant-time comparison of *key* against the stored key.

        Parameters
        ----------
        key : str
            The API key to validate.

        Returns
        -------
        bool
            ``True`` if *key* matches the stored key.
        """
        if self._key is None:
            return False
        return secrets.compare_digest(self._key, key)

    @property
    def key(self) -> str | None:
        """Return the stored API key, or ``None`` if not loaded."""
        return self._key

    @property
    def key_prefix(self) -> str:
        """Return the first 8 characters of the key for display hints.

        Returns
        -------
        str
            The prefix, or ``"<not-loaded>"`` if the key is not available.
        """
        return (self._key or "<not-loaded>")[:8]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_or_generate(self) -> None:
        """Load an existing key or generate a new one.

        Priority order:
        1. ``ANVIL_API_KEY`` environment variable (read once, then popped).
        2. Persisted key file on disk.
        3. Generate a new key via ``secrets.token_urlsafe(32)``.
        """
        env_key = os.environ.get("ANVIL_API_KEY")
        if env_key:
            self._key = env_key
            os.environ.pop("ANVIL_API_KEY", None)
            logger.debug("Using API key from ANVIL_API_KEY environment variable")
            return

        if self._key_path.exists():
            self._key = self._key_path.read_text(encoding="utf-8").strip()
            logger.debug("Loaded API key from %s", self._key_path)
            return

        self._key = secrets.token_urlsafe(32)
        self._persist()
        # Emit ONLY a short prefix hint to stderr (NOT to log files).
        print(
            f"[anvil] API key generated: {self.key_prefix}..."
            f" (use 'anvil --show-api-key' to retrieve)",
            file=sys.stderr,
            flush=True,
        )

    def _persist(self) -> None:
        """Persist the current key to a ``0600``-permission state file."""
        if self._key is None:
            return
        self._key_path.parent.mkdir(parents=True, exist_ok=True)
        self._key_path.write_text(self._key, encoding="utf-8")
        self._key_path.chmod(0o600)
        logger.debug("Persisted API key to %s", self._key_path)
