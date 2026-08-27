"""Unit tests for Discord GuildSettings model and service logic."""

from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.database.base import Base
from app.modules.guild_settings.models import GuildSettings
from app.modules.guild_settings.service import (
    get_guild_settings,
    get_or_create_guild_settings,
    update_guild_settings,
)


def test_guild_settings_model_metadata_registered() -> None:
    """Verifies that the GuildSettings model is registered in Base.metadata under 'guild_settings'."""
    assert "guild_settings" in Base.metadata.tables
    table = Base.metadata.tables["guild_settings"]

    column_names = {col.name for col in table.columns}
    expected_columns = {"id", "guild_id", "feature_enabled", "created_at", "updated_at"}
    assert expected_columns.issubset(column_names)


def test_guild_id_foreign_key_and_unique_constraint() -> None:
    """Verifies guild_id foreign key references guilds.id and has unique constraint."""
    table = Base.metadata.tables["guild_settings"]
    col = table.c.guild_id

    # Check foreign key
    fk_targets = {fk.target_fullname for fk in table.foreign_keys}
    assert "guilds.id" in fk_targets

    # Check unique constraint / index
    assert col.unique is True or any(
        col.name in idx.columns for idx in table.indexes if idx.unique
    )


def test_feature_enabled_default_behavior() -> None:
    """Verifies default values for feature_enabled in model definition."""
    table = Base.metadata.tables["guild_settings"]
    col = table.c.feature_enabled

    assert col.nullable is False
    assert col.default.arg is True


@pytest.mark.asyncio
async def test_get_guild_settings_query() -> None:
    """Verifies get_guild_settings executes expected query and returns matching record."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    guild_id = uuid.uuid4()
    existing_settings = GuildSettings(guild_id=guild_id, feature_enabled=True)
    mock_result.scalar_one_or_none.return_value = existing_settings
    mock_session.execute.return_value = mock_result

    settings = await get_guild_settings(mock_session, guild_id)

    assert settings is existing_settings
    mock_session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_or_create_guild_settings_creates_new() -> None:
    """Verifies get_or_create_guild_settings creates and persists default settings when non-existent."""
    mock_session = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.flush = AsyncMock()

    mock_nested_cm = MagicMock()
    mock_nested_cm.__aenter__ = AsyncMock(return_value=mock_nested_cm)
    mock_nested_cm.__aexit__ = AsyncMock(return_value=None)
    mock_session.begin_nested.return_value = mock_nested_cm

    guild_id = uuid.uuid4()
    settings, created = await get_or_create_guild_settings(
        session=mock_session,
        guild_id=guild_id,
    )

    assert created is True
    assert settings.guild_id == guild_id
    assert settings.feature_enabled is True
    mock_session.add.assert_called_once_with(settings)
    mock_session.flush.assert_awaited_once()
    mock_session.begin_nested.assert_called_once()


@pytest.mark.asyncio
async def test_get_or_create_guild_settings_returns_existing_unchanged() -> None:
    """Verifies existing GuildSettings is returned unchanged with created=False."""
    mock_session = AsyncMock()
    guild_id = uuid.uuid4()
    existing = GuildSettings(guild_id=guild_id, feature_enabled=True)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing
    mock_session.execute.return_value = mock_result

    settings, created = await get_or_create_guild_settings(
        session=mock_session,
        guild_id=guild_id,
    )

    assert created is False
    assert settings == existing
    mock_session.add.assert_not_called()
    mock_session.flush.assert_not_called()


@pytest.mark.asyncio
async def test_update_guild_settings_updates_feature_enabled() -> None:
    """Verifies update_guild_settings updates feature_enabled field when provided."""
    mock_session = AsyncMock()
    guild_id = uuid.uuid4()
    existing = GuildSettings(guild_id=guild_id, feature_enabled=True)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing
    mock_session.execute.return_value = mock_result
    mock_session.flush = AsyncMock()

    settings = await update_guild_settings(
        session=mock_session,
        guild_id=guild_id,
        feature_enabled=False,
    )

    assert settings.feature_enabled is False
    mock_session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_guild_settings_does_not_overwrite_unspecified() -> None:
    """Verifies update_guild_settings does not flush or overwrite fields when unspecified (None)."""
    mock_session = AsyncMock()
    guild_id = uuid.uuid4()
    existing = GuildSettings(guild_id=guild_id, feature_enabled=True)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing
    mock_session.execute.return_value = mock_result
    mock_session.flush = AsyncMock()

    settings = await update_guild_settings(
        session=mock_session,
        guild_id=guild_id,
        feature_enabled=None,
    )

    assert settings.feature_enabled is True
    mock_session.flush.assert_not_called()


@pytest.mark.asyncio
async def test_get_or_create_guild_settings_recovers_from_race_condition() -> None:
    """Verifies IntegrityError during nested savepoint insertion recovers safely by re-querying."""
    mock_session = MagicMock()
    guild_id = uuid.uuid4()

    concurrent_settings = GuildSettings(guild_id=guild_id, feature_enabled=True)
    mock_result_1 = MagicMock()
    mock_result_1.scalar_one_or_none.return_value = None

    mock_result_2 = MagicMock()
    mock_result_2.scalar_one_or_none.return_value = concurrent_settings

    mock_session.execute = AsyncMock(side_effect=[mock_result_1, mock_result_2])
    mock_session.flush = AsyncMock(side_effect=[IntegrityError("duplicate key", params=None, orig=Exception()), None])

    mock_nested_cm = MagicMock()
    mock_nested_cm.__aenter__ = AsyncMock(return_value=mock_nested_cm)
    mock_nested_cm.__aexit__ = AsyncMock(return_value=False)
    mock_session.begin_nested.return_value = mock_nested_cm

    settings, created = await get_or_create_guild_settings(
        session=mock_session,
        guild_id=guild_id,
    )

    assert created is False
    assert settings == concurrent_settings
    mock_session.begin_nested.assert_called_once()
    assert mock_session.execute.await_count == 2
