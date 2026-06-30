"""Unit tests for SecretRotationService (rotation, sweep, expire, status).

Covers tasks T027 through T032 from the 058 At-Rest Secret Encryption spec.
All external dependencies are mocked — no real DB, encryption, or key ring I/O.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from anvil.services._shared.encryption_errors import (
    RotationInProgressError,
    SweepIncompleteError,
)
from anvil.services._shared.key_ring import KeyRing
from anvil.services.secrets.secret_rotation_service import SecretRotationService


@pytest.fixture
def mock_repo() -> MagicMock:
    """Mock UserSecretRepository with async stubs."""
    repo = MagicMock()
    repo.count_by_key_id = AsyncMock(return_value=0)
    repo.iterate_by_key_id = AsyncMock()
    repo.upsert = AsyncMock()
    return repo


@pytest.fixture
def mock_enc_svc() -> MagicMock:
    """Mock EncryptionService Protocol (sync encrypt/decrypt)."""
    svc = MagicMock()
    svc.encrypt = MagicMock(return_value="encrypted_value")
    svc.decrypt = MagicMock(return_value="plaintext_value")
    return svc


@pytest.fixture
def ring() -> KeyRing:
    """A KeyRing in single-key state with no previous key."""
    return KeyRing(current="k1", previous=None, keys={"k1": b"x" * 32})


@pytest.fixture
def ring_with_previous() -> KeyRing:
    """A KeyRing in rotation overlap state (current + previous)."""
    return KeyRing(current="k2", previous="k1", keys={"k1": b"x" * 32, "k2": b"y" * 32})


@pytest.fixture
def svc(
    mock_repo: MagicMock,
    mock_enc_svc: MagicMock,
    ring: KeyRing,
) -> SecretRotationService:
    """SecretRotationService with all dependencies mocked."""
    return SecretRotationService(
        user_secret_repo=mock_repo,
        encryption_service=mock_enc_svc,
        key_ring=ring,
    )


@pytest.fixture
def svc_with_previous(
    mock_repo: MagicMock,
    mock_enc_svc: MagicMock,
    ring_with_previous: KeyRing,
) -> SecretRotationService:
    """SecretRotationService in rotation overlap state."""
    return SecretRotationService(
        user_secret_repo=mock_repo,
        encryption_service=mock_enc_svc,
        key_ring=ring_with_previous,
    )


##############################################################################
# rotate()
##############################################################################


@pytest.mark.asyncio
async def test_rotate_promotes_and_mints_new_key(
    svc: SecretRotationService,
    ring: KeyRing,
) -> None:
    """Calling rotate() promotes current→previous and mints a different key.

    Verifies:
    - old current becomes new previous
    - new current is a fresh UUID string
    - new current is NOT equal to old current
    - new current is present in the keys dict
    - returned kid is the new current
    """
    old_current = ring.current
    assert ring.previous is None

    new_kid = await svc.rotate()

    assert ring.previous == old_current
    assert ring.current == new_kid
    assert ring.current != old_current
    assert ring.current in ring.keys
    assert isinstance(new_kid, str) and len(new_kid) > 0


@pytest.mark.asyncio
async def test_rotate_raises_when_rotation_in_progress(
    svc_with_previous: SecretRotationService,
) -> None:
    """A second rotate() before expire_previous() raises RotationInProgressError."""
    with pytest.raises(RotationInProgressError):
        await svc_with_previous.rotate()


##############################################################################
# expire_previous()
##############################################################################


@pytest.mark.asyncio
async def test_expire_previous_raises_when_rows_exist(
    svc_with_previous: SecretRotationService,
    mock_repo: MagicMock,
) -> None:
    """expire_previous() raises SweepIncompleteError when rows reference previous kid."""
    mock_repo.count_by_key_id.return_value = 5

    with pytest.raises(SweepIncompleteError) as exc_info:
        await svc_with_previous.expire_previous()

    assert "5" in str(exc_info.value)
    mock_repo.count_by_key_id.assert_awaited_once()


@pytest.mark.asyncio
async def test_expire_previous_succeeds_when_zero_rows(
    svc_with_previous: SecretRotationService,
    ring_with_previous: KeyRing,
    mock_repo: MagicMock,
) -> None:
    """expire_previous() succeeds and removes previous key when no rows reference it."""
    mock_repo.count_by_key_id.return_value = 0
    old_previous = ring_with_previous.previous

    expired_kid = await svc_with_previous.expire_previous()

    assert expired_kid == old_previous
    assert ring_with_previous.previous is None
    assert old_previous not in ring_with_previous.keys
    mock_repo.count_by_key_id.assert_awaited_once_with(old_previous)


@pytest.mark.asyncio
async def test_expire_previous_returns_none_when_no_previous(
    svc: SecretRotationService,
) -> None:
    """expire_previous() returns None when there is no previous key."""
    result = await svc.expire_previous()
    assert result is None


##############################################################################
# reencrypt_sweep()
##############################################################################


@pytest.mark.asyncio
async def test_reencrypt_sweep_returns_zero_when_no_previous(
    svc: SecretRotationService,
) -> None:
    """reencrypt_sweep() returns 0 immediately when there is no previous key."""
    count = await svc.reencrypt_sweep()
    assert count == 0


##############################################################################
# rotation_status() / rotation_status_with_counts()
##############################################################################


@pytest.mark.asyncio
async def test_rotation_status_returns_ring_state(
    svc: SecretRotationService,
    ring: KeyRing,
) -> None:
    """rotation_status() returns a dict with current and previous keys."""
    status = svc.rotation_status()
    assert status["current"] == ring.current
    assert status["previous"] == ring.previous


@pytest.mark.asyncio
async def test_rotation_status_with_counts_includes_rows_by_kid(
    svc: SecretRotationService,
    ring: KeyRing,
    mock_repo: MagicMock,
) -> None:
    """rotation_status_with_counts() includes rows_by_kid mapping."""
    mock_repo.count_by_key_id.side_effect = [3, 0]

    status = await svc.rotation_status_with_counts()

    assert status["current"] == ring.current
    assert status["previous"] == ring.previous
    assert "rows_by_kid" in status
    assert ring.current in status["rows_by_kid"]
    assert mock_repo.count_by_key_id.await_count >= 1


##############################################################################
# Log safety (FR-030)
##############################################################################


@pytest.mark.asyncio
async def test_log_safety(
    svc: SecretRotationService,
    ring: KeyRing,
) -> None:
    """Rotation logs contain only kid IDs and counts — never plaintext or key material.

    Patches the module-level logger and verifies no log call includes raw
    key bytes, hex key material (64+ consecutive hex chars), or
    the word "plaintext".
    """
    with patch("anvil.services.secrets.secret_rotation_service.logger") as mock_logger:
        await svc.rotate()

        for _call in mock_logger.method_calls:
            args = " ".join(str(a) for a in _call.args if isinstance(a, str))
            assert "b'" not in args and 'b"' not in args
            for word in args.split():
                long_hex = len(word) >= 64 and all(
                    c in "0123456789abcdef" for c in word.lower()
                )
                assert not long_hex, f"Potential key material in log: {word}"
            assert "plaintext" not in args.lower()
