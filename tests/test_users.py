"""Unit tests for Discord User Identity model and service logic."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import BigInteger
from sqlalchemy.exc import IntegrityError

from app.database.base import Base
from app.modules.users.models import User
from app.modules.users.service import get_or_create_user, get_user_by_discord_id


def test_user_model_metadata_registered() -> None:
    """Verifies that the User model is registered in Base.metadata under 'users'."""
    assert "users" in Base.metadata.tables
    table = Base.metadata.tables["users"]

    column_names = {col.name for col in table.columns}
    expected_columns = {"id", "discord_user_id", "username", "global_name", "created_at", "updated_at"}
    assert expected_columns.issubset(column_names)


def test_discord_user_id_column_constraints() -> None:
    """Verifies that discord_user_id column is BigInteger, non-nullable, and has unique constraint."""
    table = Base.metadata.tables["users"]
    col = table.c.discord_user_id

    assert isinstance(col.type, BigInteger)
    assert col.nullable is False
    assert col.unique is True or any(
        col.name in idx.columns for idx in table.indexes if idx.unique
    )


@pytest.mark.asyncio
async def test_get_user_by_discord_id_query() -> None:
    """Verifies get_user_by_discord_id executes expected query and returns matching user."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    existing_user = User(discord_user_id=111222333444555666, username="alice")
    mock_result.scalar_one_or_none.return_value = existing_user
    mock_session.execute.return_value = mock_result

    user = await get_user_by_discord_id(mock_session, 111222333444555666)

    assert user is existing_user
    mock_session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_or_create_user_creates_new_user() -> None:
    """Verifies get_or_create_user creates and persists a new User when non-existent."""
    mock_session = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.flush = AsyncMock()

    mock_nested_cm = MagicMock()
    mock_nested_cm.__aenter__ = AsyncMock(return_value=mock_nested_cm)
    mock_nested_cm.__aexit__ = AsyncMock(return_value=None)
    mock_session.begin_nested.return_value = mock_nested_cm

    user, created = await get_or_create_user(
        session=mock_session,
        discord_user_id=123456789012345678,
        username="newuser",
        global_name="New User",
    )

    assert created is True
    assert user.discord_user_id == 123456789012345678
    assert user.username == "newuser"
    assert user.global_name == "New User"
    mock_session.add.assert_called_once_with(user)
    mock_session.flush.assert_awaited_once()
    mock_session.begin_nested.assert_called_once()


@pytest.mark.asyncio
async def test_get_or_create_user_returns_existing_unchanged_user() -> None:
    """Verifies existing user with unchanged data is returned without unnecessary flush calls."""
    mock_session = AsyncMock()
    existing = User(
        discord_user_id=123456789012345678,
        username="existinguser",
        global_name="Existing User",
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing
    mock_session.execute.return_value = mock_result

    user, created = await get_or_create_user(
        session=mock_session,
        discord_user_id=123456789012345678,
        username="existinguser",
        global_name="Existing User",
    )

    assert created is False
    assert user == existing
    mock_session.add.assert_not_called()
    mock_session.flush.assert_not_called()


@pytest.mark.asyncio
async def test_get_or_create_user_updates_username_when_changed() -> None:
    """Verifies existing user username is updated and flushed when Discord username changes."""
    mock_session = AsyncMock()
    existing = User(
        discord_user_id=123456789012345678,
        username="oldusername",
        global_name="Display Name",
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing
    mock_session.execute.return_value = mock_result

    user, created = await get_or_create_user(
        session=mock_session,
        discord_user_id=123456789012345678,
        username="newusername",
        global_name="Display Name",
    )

    assert created is False
    assert user.username == "newusername"
    mock_session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_or_create_user_updates_global_name_when_changed() -> None:
    """Verifies existing user global_name is updated and flushed when changed."""
    mock_session = AsyncMock()
    existing = User(
        discord_user_id=123456789012345678,
        username="samename",
        global_name="Old Global Name",
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing
    mock_session.execute.return_value = mock_result

    user, created = await get_or_create_user(
        session=mock_session,
        discord_user_id=123456789012345678,
        username="samename",
        global_name="New Global Name",
    )

    assert created is False
    assert user.global_name == "New Global Name"
    mock_session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_or_create_user_recovers_from_race_condition_integrity_error() -> None:
    """Verifies IntegrityError during nested savepoint insertion recovers safely by re-querying."""
    mock_session = MagicMock()

    concurrent_user = User(
        discord_user_id=123456789012345678,
        username="concurrent_user",
        global_name="Concurrent User",
    )
    mock_result_1 = MagicMock()
    mock_result_1.scalar_one_or_none.return_value = None

    mock_result_2 = MagicMock()
    mock_result_2.scalar_one_or_none.return_value = concurrent_user

    mock_session.execute = AsyncMock(side_effect=[mock_result_1, mock_result_2])
    mock_session.flush = AsyncMock(side_effect=[IntegrityError("duplicate key", params=None, orig=Exception()), None])

    mock_nested_cm = MagicMock()
    mock_nested_cm.__aenter__ = AsyncMock(return_value=mock_nested_cm)
    mock_nested_cm.__aexit__ = AsyncMock(return_value=False)
    mock_session.begin_nested.return_value = mock_nested_cm

    user, created = await get_or_create_user(
        session=mock_session,
        discord_user_id=123456789012345678,
        username="concurrent_user",
        global_name="Concurrent User",
    )

    assert created is False
    assert user == concurrent_user
    mock_session.begin_nested.assert_called_once()
    assert mock_session.execute.await_count == 2
