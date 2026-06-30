# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""AES-256-GCM encryption for per-user secret values.

The master key follows the same lifecycle as ``ApiKeyStore``:
1. ``ANVIL_MASTER_SECRET`` env var (read once, then popped from environ)
2. Auto-generated ``secrets.token_urlsafe(32)`` persisted to ``data/.master_key``
   with ``0600`` permissions on first boot

The ``cryptography`` library (already a transitive dependency via mlflow)
provides AES-256-GCM authenticated encryption.
"""

from __future__ import annotations

import base64
import logging
import os
import secrets
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)

_MASTER_KEY_FILE = Path("data/.master_key")
"""Default path for the persisted master encryption key."""


class EncryptionService:
    """Encrypts and decrypts per-user secret values with AES-256-GCM.

    Uses a 256-bit master key derived from ``ANVIL_MASTER_SECRET`` env var
    or auto-generated and persisted with ``0600`` permissions on first boot.
    Each encryption operation generates a fresh 96-bit random nonce.

    Parameters
    ----------
    key_path : str or Path, optional
        Path to the master key file. Defaults to ``data/.master_key``.
    """

    def __init__(self, key_path: str | Path | None = None) -> None:
        self._key_path = Path(key_path) if key_path else _MASTER_KEY_FILE
        self._key_bytes: bytes | None = None
        self._load_or_generate()

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a plaintext string with AES-256-GCM.

        Parameters
        ----------
        plaintext : str
            The secret value to encrypt.

        Returns
        -------
        str
            Base64-encoded ``nonce + ciphertext`` token.
        """
        assert self._key_bytes is not None
        nonce = secrets.token_bytes(12)
        aesgcm = AESGCM(self._key_bytes)
        ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        return base64.b64encode(nonce + ct).decode("ascii")

    def decrypt(self, token: str) -> str:
        """Decrypt a base64-encoded AES-256-GCM token.

        Parameters
        ----------
        token : str
            Base64-encoded ``nonce + ciphertext`` produced by :meth:`encrypt`.

        Returns
        -------
        str
            The original plaintext.

        Raises
        ------
        ValueError
            If the token is malformed, the key is wrong, or the
            AEAD authentication tag is invalid.
        """
        assert self._key_bytes is not None
        data = base64.b64decode(token)
        if len(data) < 13:
            raise ValueError("Token too short: missing nonce or ciphertext")
        nonce, ct = data[:12], data[12:]
        aesgcm = AESGCM(self._key_bytes)
        try:
            return aesgcm.decrypt(nonce, ct, None).decode("utf-8")
        except InvalidTag as exc:
            raise ValueError("Decryption failed: invalid key or tampered data") from exc

    ####################################################################
    # Internal helpers
    ####################################################################

    def _load_or_generate(self) -> None:
        """Load the master key or generate a new one.

        Priority:
        1. ``ANVIL_MASTER_SECRET`` env var (popped after reading).
        2. Persisted key file on disk.
        3. Generate a new key via ``secrets.token_urlsafe(32)``.
        """
        env_key = os.environ.get("ANVIL_MASTER_SECRET")
        if env_key:
            self._key_bytes = bytes.fromhex(env_key)
            os.environ.pop("ANVIL_MASTER_SECRET", None)
            logger.debug("Using master key from ANVIL_MASTER_SECRET environment")
            return

        if self._key_path.exists():
            raw = self._key_path.read_text(encoding="utf-8").strip()
            self._key_bytes = bytes.fromhex(raw)
            logger.debug("Loaded master key from %s", self._key_path)
            return

        self._key_bytes = secrets.token_bytes(32)
        self._persist()
        logger.debug("Generated and persisted new master key to %s", self._key_path)

    def _persist(self) -> None:
        """Persist the master key with ``0600`` permissions."""
        if self._key_bytes is None:
            return
        self._key_path.parent.mkdir(parents=True, exist_ok=True)
        self._key_path.write_text(self._key_bytes.hex(), encoding="utf-8")
        self._key_path.chmod(0o600)
