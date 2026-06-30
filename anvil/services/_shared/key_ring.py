# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Key ring — current and optional previous key with material lookup.

Mirrors the ``{current, previous}`` dual-key pattern established for
SSE/Redis secret rotators (spec 037).
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_KEY_RING_PATH = Path("data/.key_ring.json")
"""Default path for the local key ring file."""

from .encryption_errors import UnknownKeyIdError  # noqa: E402


class KeyRing:
    """A rotatable key ring with ``current`` and optional ``previous`` keys.

    ``current`` is always present and used for encryption.
    ``previous`` exists during the rotation overlap window.
    Keys are 256-bit (32-byte) AES-256 material identified by UUID4 strings.

    Parameters
    ----------
    current : str
        Key ID of the active encryption key.
    previous : str | None
        Key ID of the previous key, or ``None`` if no rotation in progress.
    keys : dict[str, bytes]
        Map of key ID → 32-byte key material.
    """

    def __init__(
        self,
        current: str,
        previous: str | None,
        keys: dict[str, bytes],
    ) -> None:
        self.current = current
        self.previous = previous
        self.keys = keys

    def resolve(self, kid: str) -> bytes:
        """Return the key material for a given key ID.

        Parameters
        ----------
        kid : str
            Key identifier from an envelope.

        Returns
        -------
        bytes
            The 32-byte AES-256 key material.

        Raises
        ------
        UnknownKeyIdError
            If ``kid`` is not in the ring.
        """
        material = self.keys.get(kid)
        if material is None:
            raise UnknownKeyIdError(f"Unknown key id: {kid}")
        return material

    def generate(self) -> str:
        """Generate a new UUID4 key and add it to the ring.

        Returns
        -------
        str
            The new key ID.
        """
        kid = str(uuid.uuid4())
        self.keys[kid] = secrets.token_bytes(32)
        return kid

    def save(self, path: str | Path | None = None) -> None:
        """Persist the key ring to a JSON file with ``0600`` perms.

        Parameters
        ----------
        path : str or Path, optional
            File path. Defaults to ``data/.key_ring.json``.
        """
        target = Path(path) if path else _DEFAULT_KEY_RING_PATH
        data: dict[str, object] = {
            "current": self.current,
            "previous": self.previous,
            "keys": {k: v.hex() for k, v in self.keys.items()},
        }
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, indent=2), encoding="utf-8")
        target.chmod(0o600)

    @classmethod
    def load(
        cls, path: str | Path | None = None, *, seed_from_env: str | None = None
    ) -> KeyRing:
        """Load a key ring from disk, env, or auto-generate.

        Priority:
        1. ``seed_from_env`` env var (hex key, popped after read).
        2. Persisted key file on disk.
        3. Auto-generated single-key ring.

        Parameters
        ----------
        path : str or Path, optional
            File path. Defaults to ``data/.key_ring.json``.
        seed_from_env : str, optional
            Env var name to seed the current key (e.g. ``"ANVIL_MASTER_SECRET"``).

        Returns
        -------
        KeyRing
            The loaded or generated key ring.
        """
        target = Path(path) if path else _DEFAULT_KEY_RING_PATH

        # 1. Env var override
        if seed_from_env is not None:
            env_key = os.environ.get(seed_from_env)
            if env_key is not None:
                kid = str(uuid.uuid4())
                keys = {kid: bytes.fromhex(env_key)}
                os.environ.pop(seed_from_env, None)
                ring = cls(current=kid, previous=None, keys=keys)
                ring.save(target)
                logger.debug("Seeded key ring from %s env var", seed_from_env)
                return ring

        # 2. Persisted file
        if target.exists():
            raw = target.read_text(encoding="utf-8")
            data = json.loads(raw)
            keys = {k: bytes.fromhex(v) for k, v in data["keys"].items()}
            logger.debug("Loaded key ring from %s", target)
            return cls(
                current=data["current"],
                previous=data.get("previous"),
                keys=keys,
            )

        # 3. Auto-generate
        kid = str(uuid.uuid4())
        keys = {kid: secrets.token_bytes(32)}
        ring = cls(current=kid, previous=None, keys=keys)
        ring.save(target)
        logger.debug("Generated new key ring at %s", target)
        return ring
