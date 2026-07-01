# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""KMS envelope encryption service for SaaS mode.

Implements the ``EncryptionService`` Protocol using AWS KMS for key
wrapping and local AES-256-GCM for data encryption (envelope
encryption). Accepts ``kms_client`` and ``ssm_client`` as constructor
dependencies for testability — no direct boto3 imports.
"""

from __future__ import annotations

import base64
import logging
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ...services._shared.encryption_envelope import EncryptionEnvelope
from ...services._shared.encryption_errors import (
    InvalidCiphertextError,
    UnknownKeyIdError,
)

logger = logging.getLogger(__name__)


class KmsEncryptionService:
    """AES-256-GCM encryption backed by a KMS-wrapped DEK ring.

    Uses envelope encryption: the data encryption key (DEK) is wrapped
    by a KMS customer master key (CMK) and unwrapped at init via
    ``kms_client.decrypt()``. All data is encrypted locally with
    AES-256-GCM using the unwrapped DEK, producing the same
    ``EncryptionEnvelope`` schema as ``LocalEncryptionService``.

    Parameters
    ----------
    kms_client : Any
        A boto3 ``kms`` client or compatible test double.
    ssm_client : Any
        A boto3 ``ssm`` client or compatible test double.
    dek_ring_config : dict[str, Any]
        DEK ring configuration. Format::

            {
                "current": "<kid>",
                "previous": "<kid>" | None,
                "keys": {
                    "<kid>": {
                        "wrapped_dek": "<base64>",
                        "kek_id": "arn:aws:kms:..."
                    }
                }
            }

    name : str, optional
        Service name for future registry pattern. Defaults to ``"kms"``.

    Raises
    ------
    RuntimeError
        If KMS is unavailable or any DEK unwrapping fails at init.
    ValueError
        If a unwrapped DEK is not exactly 32 bytes (AES-256).
    """

    def __init__(
        self,
        kms_client: Any,
        ssm_client: Any,
        dek_ring_config: dict[str, Any],
        name: str = "kms",
    ) -> None:
        self._kms = kms_client
        self._ssm = ssm_client
        self.name = name
        self._current: str = dek_ring_config["current"]
        self._previous: str | None = dek_ring_config.get("previous")
        self._keys: dict[str, bytes] = {}

        keys_config = dek_ring_config["keys"]
        for kid, key_info in keys_config.items():
            wrapped = base64.b64decode(key_info["wrapped_dek"])
            try:
                response = self._kms.decrypt(CiphertextBlob=wrapped)
            except Exception as exc:
                raise RuntimeError(f"KMS decrypt failed for key {kid}: {exc}") from exc
            plaintext: bytes = response["Plaintext"]
            if len(plaintext) != 32:
                raise ValueError(
                    f"Expected 32-byte DEK for {kid}, got {len(plaintext)}"
                )
            self._keys[kid] = plaintext

        logger.debug(
            "KmsEncryptionService initialized: current=%s, keys=%s",
            self._current,
            list(self._keys),
        )

    ####################################################################
    # Public API
    ####################################################################

    def encrypt(self, plaintext: str, aad: bytes) -> str:
        """Encrypt plaintext with AES-256-GCM, return envelope token.

        Parameters
        ----------
        plaintext : str
            UTF-8 secret value to encrypt.
        aad : bytes
            Additional Authenticated Data (``user_id:key``).

        Returns
        -------
        str
            JSON-serialized ``EncryptionEnvelope`` string.
        """
        key = self._keys[self._current]
        nonce = __import__("secrets").token_bytes(12)
        aesgcm = AESGCM(key)
        ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), aad)
        env = EncryptionEnvelope(
            kid=self._current,
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
        InvalidCiphertextError
            Tampered ciphertext, auth tag mismatch, or AAD mismatch.
        UnknownKeyIdError
            Envelope ``kid`` not found in the in-memory DEK ring.
        """
        env = EncryptionEnvelope.from_token(token)
        key = self._keys.get(env.kid)
        if key is None:
            raise UnknownKeyIdError(f"Unknown key id: {env.kid}")
        nonce = base64.b64decode(env.n)
        ct = base64.b64decode(env.ct)
        aesgcm = AESGCM(key)
        try:
            return aesgcm.decrypt(nonce, ct, aad).decode("utf-8")
        except InvalidTag as exc:
            raise InvalidCiphertextError(
                "Decryption failed: invalid key, tampered data, " "or AAD mismatch"
            ) from exc
