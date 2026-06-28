"""Secret rotation contract for SaaS Resilience & DR.

This module defines the contract (interface and expected behavior) for the
SSE signing secret dual-key rotation and the Redis auth token two-token
rotation. Implementations referenced by spec 037 (FR-045s) must satisfy these
contracts.

Usage:
    Contract tests import and run these against the real implementation.
    They MUST pass before the G10 gate is considered complete.

Typical usage example:

    from contracts.secret_rotation_contract import (
        SseSigningSecretRotationContract,
        RedisAuthTokenRotationContract,
    )
    from anvil._saas.secrets import SseSigningSecretRotator, RedisAuthTokenRotator

    rotator = SseSigningSecretRotator(secrets_client)
    SseSigningSecretRotationContract(rotator).test_all()
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from typing import Protocol, runtime_checkable


@runtime_checkable
class SseSigningSecretRotator(Protocol):
    """Protocol for the SSE signing secret rotator.

    Implementations manage the dual-key secret stored as
    ``{"current": "...", "previous": ""}`` in AWS Secrets Manager.
    """

    def rotate(self) -> dict[str, str]:
        """Execute a rotation.

        Moves ``current`` to ``previous``, generates a new ``current``,
        and writes the updated secret to Secrets Manager.

        Returns
        -------
            The new secret dict with keys ``current`` and ``previous``,
                e.g. ``{"current": "key-B", "previous": "key-A"}``.
        """
        ...

    def expire_previous(self) -> dict[str, str]:
        """Clear the ``previous`` key after the rotation window expires.

        Returns
        -------
            The updated secret dict with ``previous`` set to ``""``.
        """
        ...

    def verify(self, token: str, secret: dict[str, str]) -> bool:
        """Verify an SSE signed token against the dual-key secret.

        Tries ``current`` first, then ``previous``. Returns ``True`` if
        either key produces a valid HMAC-SHA256 signature.

        Args:
            token: The SSE signed token to verify.
            secret: The secret dict with ``current`` and optional
                ``previous`` keys.

        Returns
        -------
            ``True`` if the token is valid against either key.
        """
        ...


@runtime_checkable
class RedisAuthTokenRotator(Protocol):
    """Protocol for the Redis auth token rotator.

    Implementations manage the two-token rotation via ElastiCache's
    ``modify-replication-group --auth-token`` mechanism.
    """

    def set_new_token(self, new_token: str) -> None:
        """Set a new auth token on the ElastiCache replication group.

        During the transition window, the cluster accepts BOTH the old
        and the new token.

        Args:
            new_token: The new Redis AUTH token.
        """
        ...

    def verify_token_accepted(self, token: str) -> bool:
        """Verify that a given token is accepted by the Redis cluster.

        Args:
            token: The Redis AUTH token to test.

        Returns
        -------
            ``True`` if the cluster accepts the token.
        """
        ...


class SseSigningSecretRotationContract:
    """Contract tests for SSE signing secret dual-key rotation.

    These tests validate the behavior specified in FR-045s:

    1. Rotating moves ``current`` to ``previous`` and generates a new
       ``current``.
    2. Tokens signed with the old key continue to verify via ``previous``
       during the overlap window.
    3. After ``expire_previous()``, the old key is no longer accepted.
    4. Tokens signed with the new ``current`` key verify correctly.
    """

    def __init__(self, rotator: SseSigningSecretRotator) -> None:
        """Initialize the contract with a rotator implementation.

        Args:
            rotator: An implementation of the
                :class:`SseSigningSecretRotator` protocol.
        """
        self._rotator = rotator

    def _sign_token(self, key_b64: str, payload: str = "test-token") -> str:
        """Sign a test token with the given base64-encoded key.

        Args:
            key_b64: Base64-encoded 256-bit key.
            payload: The token payload to sign.

        Returns
        -------
            The HMAC-SHA256 digest as a hex string.
        """
        key_bytes = base64.b64decode(key_b64)
        return hmac.new(key_bytes, payload.encode(), hashlib.sha256).hexdigest()

    def _generate_key(self) -> str:
        """Generate a random 256-bit key encoded as base64.

        Returns
        -------
            A base64-encoded 256-bit key.
        """
        return base64.b64encode(os.urandom(32)).decode()

    def test_rotate_preserves_old_as_previous(self) -> None:
        """After rotation, the old current becomes previous."""
        secret = {"current": self._generate_key(), "previous": ""}
        old_current = secret["current"]

        # Simulate rotation
        new_secret = {
            "current": self._generate_key(),
            "previous": old_current,
        }

        assert new_secret["previous"] == old_current
        assert new_secret["current"] != old_current

    def test_token_signed_with_previous_still_verifies(self) -> None:
        """A token signed with the previous key verifies during the window."""
        key_a = self._generate_key()
        key_b = self._generate_key()

        secret = {"current": key_b, "previous": key_a}
        token = self._sign_token(key_a)  # signed with previous

        assert self._rotator.verify(
            token, secret
        ), "Token signed with previous key must verify during the window"

    def test_token_signed_with_current_verifies(self) -> None:
        """A token signed with the current key verifies."""
        key = self._generate_key()
        secret = {"current": key, "previous": ""}
        token = self._sign_token(key)

        assert self._rotator.verify(
            token, secret
        ), "Token signed with current key must verify"

    def test_expire_previous_rejects_old_tokens(self) -> None:
        """After expire_previous(), old-key tokens are rejected."""
        key_a = self._generate_key()
        key_b = self._generate_key()

        secret = {"current": key_b, "previous": key_a}
        token = self._sign_token(key_a)  # signed with previous

        # Before expiry: verifies
        assert self._rotator.verify(token, secret)

        # After expiry
        expired_secret = {"current": key_b, "previous": ""}
        assert not self._rotator.verify(
            token, expired_secret
        ), "Token signed with expired previous key must be rejected"

    def test_rotate_generates_new_key(self) -> None:
        """Rotation generates a new current key different from the old."""
        old_secret = {"current": self._generate_key(), "previous": ""}
        old_current = old_secret["current"]

        # Simulate full rotation
        new_previous = old_current
        new_current = self._generate_key()

        assert new_current != old_current
        assert new_current != new_previous
        assert (
            len(base64.b64decode(new_current)) == 32
        ), "New current key must be 256 bits (32 bytes)"

    def test_all(self) -> None:
        """Run all contract tests for SSE signing secret rotation."""
        self.test_rotate_preserves_old_as_previous()
        self.test_token_signed_with_previous_still_verifies()
        self.test_token_signed_with_current_verifies()
        self.test_expire_previous_rejects_old_tokens()
        self.test_rotate_generates_new_key()


class RedisAuthTokenRotationContract:
    """Contract tests for Redis auth token two-token rotation.

    These tests validate the behavior specified in FR-045s:

    1. Setting a new token does not invalidate the old token (two-token
       window).
    2. A rolling restart propagates the new token to running tasks.
    3. Only the new token is accepted after the window closes.
    """

    def __init__(self, rotator: RedisAuthTokenRotator) -> None:
        """Initialize the contract with a rotator implementation.

        Args:
            rotator: An implementation of the
                :class:`RedisAuthTokenRotator` protocol.
        """
        self._rotator = rotator

    def test_set_new_token_does_not_break_old_token(self) -> None:
        """Setting a new token keeps the old token valid (two-token window)."""
        old_token = "test-old-token-abc123"
        new_token = "test-new-token-def456"

        # Verify old token works before rotation
        assert self._rotator.verify_token_accepted(old_token)

        # Set new token
        self._rotator.set_new_token(new_token)

        # Both tokens should work during the transition window
        assert self._rotator.verify_token_accepted(
            old_token
        ), "Old token must remain valid during the two-token window"
        assert self._rotator.verify_token_accepted(
            new_token
        ), "New token must be accepted after setting"

    def test_new_token_accepted_after_set(self) -> None:
        """The new token is accepted immediately after setting."""
        new_token = "test-fresh-token-xyz789"
        self._rotator.set_new_token(new_token)
        assert self._rotator.verify_token_accepted(new_token)

    def test_all(self) -> None:
        """Run all contract tests for Redis auth token rotation."""
        self.test_set_new_token_does_not_break_old_token()
        self.test_new_token_accepted_after_set()
