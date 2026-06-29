# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""UserSecret service contract — encrypted per-user secret storage.

Manages sensitive user credentials (HuggingFace token, API keys) that
remote services consume. Values are encrypted at rest using AES-256-GCM.
"""

from __future__ import annotations

from typing import Protocol


class UserSecretService(Protocol):
    """Manage per-user encrypted secrets.

    Secrets are scoped by user + key name. Key names follow a dot-separated
    convention (e.g. ``"hf_token"``, ``"openai.api_key"``).

    Encrypted values use AES-256-GCM with the project master key
    (``ANVIL_MASTER_SECRET`` env var or auto-generated + ``0600`` file).
    """

    async def get_secret(self, user_id: str, key: str) -> str | None:
        """Return the decrypted value for a user+key.

        Returns ``None`` if the secret does not exist (not an error —
        caller should fall back to env var).
        """
        ...

    async def set_secret(self, user_id: str, key: str, value: str) -> None:
        """Encrypt and store (upsert) a secret for a user+key."""
        ...

    async def delete_secret(self, user_id: str, key: str) -> None:
        """Remove a secret entry. Idempotent — no error if missing."""
        ...

    async def list_keys(self, user_id: str) -> list[str]:
        """List all secret key names for a user. Never returns values."""
        ...

    async def resolve_token(self, user_id: str, key: str, env_var: str) -> str | None:
        """Resolve a credential via precedence chain: UserSecret > env var.

        Returns ``None`` only if neither source has the credential
        (caller should produce an actionable "configure token" message).
        """
        ...
