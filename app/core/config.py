"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Production application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Required settings
    DISCORD_TOKEN: str = Field(
        ...,
        description="Required Discord bot token from developer portal.",
    )
    DATABASE_URL: SecretStr = Field(
        ...,
        description="Required PostgreSQL connection string (postgresql+asyncpg://...).",
    )

    # Optional settings
    DISCORD_GUILD_ID: int | None = Field(
        default=None,
        description="Optional Guild ID for instant slash command sync during development.",
    )
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).",
    )
    ENVIRONMENT: Literal["development", "production", "staging"] = Field(
        default="production",
        description="Deployment environment name.",
    )

    @field_validator("DISCORD_TOKEN")
    @classmethod
    def validate_discord_token(cls, v: str) -> str:
        token = v.strip()
        if not token or token == "your_discord_bot_token_here":
            raise ValueError(
                "DISCORD_TOKEN is missing or contains default placeholder. "
                "Provide a valid Discord bot token."
            )
        return token

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper().strip()
        if upper not in valid_levels:
            raise ValueError(
                f"Invalid LOG_LEVEL '{v}'. Must be one of: {', '.join(sorted(valid_levels))}"
            )
        return upper

    @property
    def database_url_str(self) -> str:
        """Returns the unmasked database connection string."""
        return self.DATABASE_URL.get_secret_value()


@lru_cache
def get_settings() -> Settings:
    """Retrieves cached application settings."""
    return Settings()
