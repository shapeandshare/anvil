# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Encryption service Protocol and local implementation.

Defines the ``EncryptionService`` Protocol (PEP 544 — structural typing)
and ``LocalEncryptionService`` for AES-256-GCM with a key ring,
self-describing envelope, and AAD bound to row identity.
"""

from __future__ import annotations

import base64
import logging
from typing import Protocol, runtime_checkable

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .encryption_envelope import EncryptionEnvelope
from .encryption_errors import InvalidCiphertextError
from .key_ring import KeyRing

logger = logging.getLogger(__name__)


@runtime_checkable
class EncryptionService(Protocol):
    """Structural protocol for at-rest secret encryption (PEP 544).

    Any object with ``encrypt(plaintext, aad)`` and ``decrypt(token, aad)``
    method signatures satisfies this protocol — no inheritance required.

    Implementations:
    - ``LocalEncryptionService`` — file/env key ring (local mode)
    - ``KmsEncryptionService`` — KMS envelope (SaaS mode, in ``anvil/_saas/``)
    """

    def encrypt(self, plaintext: str, aad: bytes) -> str:
        r"""Encrypt plaintext with AAD, return envelope token.

        Parameters
        ----------
        plaintext : str
            UTF-8 secret value to encrypt.
        aad : bytes
            Additional Authenticated Data. Callers MUST supply
            ``f\"{user_id}:{key}\".encode()``.

        Returns
        -------
        str
            JSON-serialized ``EncryptionEnvelope`` string.
        """
        ...

    def decrypt(self, token: str, aad: bytes) -> str:
        """Decrypt envelope token with AAD, return plaintext.

        Parameters
        ----------
        token : str
            JSON-serialized ``EncryptionEnvelope``.
        aad : bytes
            AAD that was used during encryption.

        Returns
        -------
        str
            The original plaintext.

        Raises
        ------
        InvalidAadError
            AAD mismatch.
        InvalidCiphertextError
            Tampered ciphertext or auth tag.
        UnknownKeyIdError
            Envelope ``kid`` not found in the active ring.
        """
        ...


class LocalEncryptionService:
    """AES-256-GCM encryption backed by a local key ring.

    Uses ``KeyRing`` for key material, ``EncryptionEnvelope`` for the
    self-describing envelope, and ``user_id:key`` AAD for row binding.

    Parameters
    ----------
    key_ring : KeyRing
        Initialized key ring with current (and optionally previous) keys.
    """

    def __init__(self, key_ring: KeyRing) -> None:
        self._key_ring = key_ring

    def encrypt(self, plaintext: str, aad: bytes) -> str:
        """Encrypt with AES-256-GCM, return envelope token.

        Parameters
        ----------
        plaintext : str
            Secret value to encrypt.
        aad : bytes
            Additional Authenticated Data (``user_id:key``).

        Returns
        -------
        str
            JSON-serialized ``EncryptionEnvelope``.
        """
        key = self._key_ring.resolve(self._key_ring.current)
        nonce = __import__("secrets").token_bytes(12)
        aesgcm = AESGCM(key)
        ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), aad)
        env = EncryptionEnvelope(
            kid=self._key_ring.current,
            n=base64.b64encode(nonce).decode("ascii"),
            ct=base64.b64encode(ct).decode("ascii"),
        )
        return env.to_token()

    def decrypt(self, token: str, aad: bytes) -> str:
        """Decrypt an envelope token.

        Parameters
        ----------
        token : str
            JSON-serialized ``EncryptionEnvelope``.
        aad : bytes
            The same AAD used during encryption.

        Returns
        -------
        str
            Decrypted plaintext.

        Raises
        ------
        InvalidAadError
            AAD mismatch (GCM authentication failure).
        InvalidCiphertextError
            Tampered ciphertext or auth tag.
        UnknownKeyIdError
            Envelope ``kid`` not in the key ring.
        """
        env = EncryptionEnvelope.from_token(token)
        key = self._key_ring.resolve(env.kid)
        nonce = base64.b64decode(env.n)
        ct = base64.b64decode(env.ct)
        aesgcm = AESGCM(key)
        try:
            return aesgcm.decrypt(nonce, ct, aad).decode("utf-8")
        except InvalidTag as exc:
            raise InvalidCiphertextError(
                "Decryption failed: invalid key, tampered data, or AAD mismatch"
            ) from exc
