"""Unit tests for Pydantic application configuration loading."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings


def test_settings_loaded_from_env() -> None:
    """Verifies that settings load expected values from environment variables."""
    settings = get_settings()
    assert settings.DISCORD_TOKEN == "test-token-not-a-real-discord-token"
    assert (
        settings.database_url_str
        == "postgresql+asyncpg://postgres:postgres@localhost:5432/refind_cloud_test"
    )
    assert settings.LOG_LEVEL == "INFO"
    assert settings.ENVIRONMENT == "development"
    assert settings.DISCORD_GUILD_ID is None


def test_optional_guild_id_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies that DISCORD_GUILD_ID parses integer values correctly."""
    monkeypatch.setenv("DISCORD_GUILD_ID", "987654321098765432")
    get_settings.cache_clear()

    settings = get_settings()
    assert settings.DISCORD_GUILD_ID == 987654321098765432


def test_missing_discord_token_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies that missing DISCORD_TOKEN raises a ValidationError."""
    monkeypatch.delenv("DISCORD_TOKEN", raising=False)
    get_settings.cache_clear()

    with pytest.raises(ValidationError) as exc_info:
        Settings()

    assert "DISCORD_TOKEN" in str(exc_info.value)


def test_placeholder_discord_token_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies that default placeholder token is explicitly rejected."""
    monkeypatch.setenv("DISCORD_TOKEN", "your_discord_bot_token_here")
    get_settings.cache_clear()

    with pytest.raises(ValidationError) as exc_info:
        Settings()

    assert "DISCORD_TOKEN is missing or contains default placeholder" in str(exc_info.value)


def test_missing_database_url_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies that missing DATABASE_URL raises a ValidationError."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_settings.cache_clear()

    with pytest.raises(ValidationError) as exc_info:
        Settings()

    assert "DATABASE_URL" in str(exc_info.value)


def test_invalid_log_level_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies that invalid LOG_LEVEL raises a ValidationError."""
    monkeypatch.setenv("LOG_LEVEL", "SUPER_VERBOSE")
    get_settings.cache_clear()

    with pytest.raises(ValidationError) as exc_info:
        Settings()

    assert "Invalid LOG_LEVEL" in str(exc_info.value)
