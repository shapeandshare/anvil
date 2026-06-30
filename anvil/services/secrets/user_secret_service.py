# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Service for managing encrypted per-user secrets.

Provides CRUD operations for ``UserSecret`` entries and a
precedence-based token resolver: ``UserSecret (DB) > env var``.
"""

from __future__ import annotations

import json
import logging
import os

from ...db.repositories.user_secret_repository import UserSecretRepository
from .._shared.encryption import EncryptionService

logger = logging.getLogger(__name__)


class UserSecretService:
    """Manage per-user encrypted secrets with env-var fallback.

    Parameters
    ----------
    user_secret_repo : UserSecretRepository
        Repository for ``UserSecret`` CRUD.
    encryption : EncryptionService
        AES-256-GCM encryption service (Protocol — structurally typed).
    """

    def __init__(
        self,
        user_secret_repo: UserSecretRepository,
        encryption: EncryptionService,
    ) -> None:
        self._repo = user_secret_repo
        self._encryption = encryption

    async def get_secret(self, user_id: str, key: str) -> str | None:
        """Return the decrypted value for a user+key.

        Parameters
        ----------
        user_id : str
            User identifier.
        key : str
            Secret key name.

        Returns
        -------
        str | None
            Decrypted value, or ``None`` if not found.
        """
        secret = await self._repo.get(user_id, key)
        if secret is None:
            return None
        aad = f"{user_id}:{key}".encode()
        return self._encryption.decrypt(secret.encrypted_value, aad)

    async def set_secret(self, user_id: str, key: str, value: str) -> None:
        """Encrypt and store (upsert) a secret.

        Parameters
        ----------
        user_id : str
            User identifier.
        key : str
            Secret key name.
        value : str
            Plaintext secret value (encrypted before storage).
        """
        aad = f"{user_id}:{key}".encode()
        encrypted = self._encryption.encrypt(value, aad)
        kid: str = json.loads(encrypted)["kid"]
        await self._repo.upsert(user_id, key, encrypted, key_id=kid)

    async def delete_secret(self, user_id: str, key: str) -> None:
        """Remove a secret entry. Idempotent.

        Parameters
        ----------
        user_id : str
            User identifier.
        key : str
            Secret key name.
        """
        await self._repo.delete(user_id, key)

    async def list_keys(self, user_id: str) -> list[str]:
        """List all secret key names for a user.

        Parameters
        ----------
        user_id : str
            User identifier.

        Returns
        -------
        list[str]
            Key names (never returns values).
        """
        secrets = await self._repo.get_all_for_user(user_id)
        return [s.key for s in secrets]

    async def resolve_token(self, user_id: str, key: str, env_var: str) -> str | None:
        """Resolve a credential via precedence: UserSecret > env var.

        Parameters
        ----------
        user_id : str
            User identifier.
        key : str
            Secret key name (e.g. ``"hf_token"``).
        env_var : str
            Environment variable name (e.g. ``"HF_TOKEN"``).

        Returns
        -------
        str | None
            The resolved token, or ``None`` if neither source has it.
        """
        db_value = await self.get_secret(user_id, key)
        if db_value is not None:
            return db_value
        return os.environ.get(env_var)
