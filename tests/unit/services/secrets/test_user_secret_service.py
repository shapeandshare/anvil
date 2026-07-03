"""Tests for UserSecretService — encrypted per-user secret management."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from anvil.services.secrets.user_secret_service import UserSecretService


class TestUserSecretService:
    """Tests for UserSecretService CRUD and token resolution."""

    @pytest.fixture
    def mock_repo(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def mock_encryption(self) -> MagicMock:
        enc = MagicMock()
        enc.encrypt.return_value = '{"kid": "key1", "ciphertext": "enc"}'
        enc.decrypt.return_value = "decrypted_value"
        return enc

    @pytest.fixture
    def service(
        self, mock_repo: AsyncMock, mock_encryption: MagicMock
    ) -> UserSecretService:
        return UserSecretService(mock_repo, mock_encryption)

    async def test_get_secret_returns_decrypted_value(
        self,
        service: UserSecretService,
        mock_repo: AsyncMock,
        mock_encryption: MagicMock,
    ) -> None:
        mock_repo.get.return_value = MagicMock(encrypted_value=b"encrypted")
        result = await service.get_secret("user1", "hf_token")
        assert result == "decrypted_value"
        mock_repo.get.assert_awaited_once_with("user1", "hf_token")
        mock_encryption.decrypt.assert_called_once()

    async def test_get_secret_returns_none_when_missing(
        self, service: UserSecretService, mock_repo: AsyncMock
    ) -> None:
        mock_repo.get.return_value = None
        result = await service.get_secret("user1", "missing")
        assert result is None

    async def test_set_secret_encrypts_and_upserts(
        self,
        service: UserSecretService,
        mock_repo: AsyncMock,
        mock_encryption: MagicMock,
    ) -> None:
        await service.set_secret("user1", "hf_token", "my_token_value")
        mock_encryption.encrypt.assert_called_once_with(
            "my_token_value", b"user1:hf_token"
        )
        mock_repo.upsert.assert_awaited_once()

    async def test_delete_secret(
        self, service: UserSecretService, mock_repo: AsyncMock
    ) -> None:
        await service.delete_secret("user1", "hf_token")
        mock_repo.delete.assert_awaited_once_with("user1", "hf_token")

    async def test_list_keys(
        self, service: UserSecretService, mock_repo: AsyncMock
    ) -> None:
        from unittest.mock import MagicMock

        s1 = MagicMock()
        s1.key = "hf_token"
        s2 = MagicMock()
        s2.key = "openai_key"
        mock_repo.get_all_for_user.return_value = [s1, s2]
        keys = await service.list_keys("user1")
        assert keys == ["hf_token", "openai_key"]

    async def test_resolve_token_prefers_db_over_env(
        self, service: UserSecretService, mock_repo: AsyncMock
    ) -> None:
        mock_repo.get.return_value = MagicMock(encrypted_value=b"enc")
        result = await service.resolve_token("user1", "hf_token", "HF_TOKEN")
        assert result == "decrypted_value"

    async def test_resolve_token_falls_back_to_env(
        self,
        service: UserSecretService,
        mock_repo: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_repo.get.return_value = None
        monkeypatch.setenv("HF_TOKEN", "env_token")
        result = await service.resolve_token("user1", "hf_token", "HF_TOKEN")
        assert result == "env_token"

    async def test_resolve_token_returns_none_when_no_source(
        self,
        service: UserSecretService,
        mock_repo: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_repo.get.return_value = None
        monkeypatch.delenv("HF_TOKEN", raising=False)
        result = await service.resolve_token("user1", "hf_token", "HF_TOKEN")
        assert result is None
