"""Pytest configuration and test environment isolation fixtures."""

from collections.abc import Generator

import pytest

from app.core.config import Settings, get_settings
from app.core.context import clear_app_context


@pytest.fixture(autouse=True)
def isolate_test_environment(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Provides isolated test environment variables and resets AppContext before and after each test.
    
    Disables .env file loading on Settings during tests so tests do not read production or VPS .env files.
    """
    clear_app_context()

    # Prevent Pydantic Settings from loading the local/production .env file during unit tests
    monkeypatch.setitem(Settings.model_config, "env_file", None)

    # Set explicit test-only environment variables
    monkeypatch.setenv("DISCORD_TOKEN", "test-token-not-a-real-discord-token")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/refind_cloud_test",
    )
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("DISCORD_GUILD_ID", raising=False)

    get_settings.cache_clear()

    yield

    clear_app_context()
    get_settings.cache_clear()


@pytest.fixture
def clear_settings_cache() -> Generator[None, None, None]:
    """Fixture ensuring the settings lru_cache is cleared after custom tests."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
