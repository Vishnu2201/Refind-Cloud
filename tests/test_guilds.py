"""Unit tests for Discord Guild identity model and service logic."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import BigInteger
from sqlalchemy.exc import IntegrityError

from app.database.base import Base
from app.modules.guilds.models import Guild
from app.modules.guilds.service import get_guild_by_discord_id, get_or_create_guild


def test_guild_model_metadata_registered() -> None:
    """Verifies that the Guild model is registered in Base.metadata under 'guilds'."""
    assert "guilds" in Base.metadata.tables
    table = Base.metadata.tables["guilds"]

    column_names = {col.name for col in table.columns}
    expected_columns = {"id", "discord_guild_id", "name", "created_at", "updated_at"}
    assert expected_columns.issubset(column_names)


def test_discord_guild_id_column_constraints() -> None:
    """Verifies that discord_guild_id column is BigInteger, non-nullable, and has unique constraint."""
    table = Base.metadata.tables["guilds"]
    col = table.c.discord_guild_id

    assert isinstance(col.type, BigInteger)
    assert col.nullable is False
    assert col.unique is True or any(
        col.name in idx.columns for idx in table.indexes if idx.unique
    )


@pytest.mark.asyncio
async def test_get_guild_by_discord_id_query() -> None:
    """Verifies get_guild_by_discord_id executes expected query and returns matching guild."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    existing_guild = Guild(discord_guild_id=987654321098765432, name="Refind Cloud HQ")
    mock_result.scalar_one_or_none.return_value = existing_guild
    mock_session.execute.return_value = mock_result

    guild = await get_guild_by_discord_id(mock_session, 987654321098765432)

    assert guild is existing_guild
    mock_session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_or_create_guild_creates_new_guild() -> None:
    """Verifies get_or_create_guild creates and persists a new Guild when non-existent."""
    mock_session = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.flush = AsyncMock()

    mock_nested_cm = MagicMock()
    mock_nested_cm.__aenter__ = AsyncMock(return_value=mock_nested_cm)
    mock_nested_cm.__aexit__ = AsyncMock(return_value=None)
    mock_session.begin_nested.return_value = mock_nested_cm

    guild, created = await get_or_create_guild(
        session=mock_session,
        discord_guild_id=987654321098765432,
        name="Refind Cloud Server",
    )

    assert created is True
    assert guild.discord_guild_id == 987654321098765432
    assert guild.name == "Refind Cloud Server"
    mock_session.add.assert_called_once_with(guild)
    mock_session.flush.assert_awaited_once()
    mock_session.begin_nested.assert_called_once()


@pytest.mark.asyncio
async def test_get_or_create_guild_returns_existing_unchanged_guild() -> None:
    """Verifies existing guild with unchanged name is returned without unnecessary flush calls."""
    mock_session = AsyncMock()
    existing = Guild(
        discord_guild_id=987654321098765432,
        name="Refind Cloud Community",
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing
    mock_session.execute.return_value = mock_result

    guild, created = await get_or_create_guild(
        session=mock_session,
        discord_guild_id=987654321098765432,
        name="Refind Cloud Community",
    )

    assert created is False
    assert guild == existing
    mock_session.add.assert_not_called()
    mock_session.flush.assert_not_called()


@pytest.mark.asyncio
async def test_get_or_create_guild_updates_name_when_changed() -> None:
    """Verifies existing guild name is updated and flushed when Discord guild name changes."""
    mock_session = AsyncMock()
    existing = Guild(
        discord_guild_id=987654321098765432,
        name="Old Server Name",
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing
    mock_session.execute.return_value = mock_result

    guild, created = await get_or_create_guild(
        session=mock_session,
        discord_guild_id=987654321098765432,
        name="New Server Name",
    )

    assert created is False
    assert guild.name == "New Server Name"
    mock_session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_or_create_guild_recovers_from_race_condition_integrity_error() -> None:
    """Verifies IntegrityError during nested savepoint insertion recovers safely by re-querying."""
    mock_session = MagicMock()

    concurrent_guild = Guild(
        discord_guild_id=987654321098765432,
        name="Concurrent Guild",
    )
    mock_result_1 = MagicMock()
    mock_result_1.scalar_one_or_none.return_value = None

    mock_result_2 = MagicMock()
    mock_result_2.scalar_one_or_none.return_value = concurrent_guild

    mock_session.execute = AsyncMock(side_effect=[mock_result_1, mock_result_2])
    mock_session.flush = AsyncMock(side_effect=[IntegrityError("duplicate key", params=None, orig=Exception()), None])

    mock_nested_cm = MagicMock()
    mock_nested_cm.__aenter__ = AsyncMock(return_value=mock_nested_cm)
    mock_nested_cm.__aexit__ = AsyncMock(return_value=False)
    mock_session.begin_nested.return_value = mock_nested_cm

    guild, created = await get_or_create_guild(
        session=mock_session,
        discord_guild_id=987654321098765432,
        name="Concurrent Guild",
    )

    assert created is False
    assert guild == concurrent_guild
    mock_session.begin_nested.assert_called_once()
    assert mock_session.execute.await_count == 2
