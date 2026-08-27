"""Unit tests for Discord Role identity model and service logic."""

from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest
from sqlalchemy import BigInteger
from sqlalchemy.exc import IntegrityError

from app.database.base import Base
from app.modules.roles.models import Role
from app.modules.roles.service import delete_role, get_or_create_role, get_role


def test_role_model_metadata_registered() -> None:
    """Verifies that the Role model is registered in Base.metadata under 'roles'."""
    assert "roles" in Base.metadata.tables
    table = Base.metadata.tables["roles"]

    column_names = {col.name for col in table.columns}
    expected_columns = {"id", "guild_id", "discord_role_id", "name", "position", "created_at", "updated_at"}
    assert expected_columns.issubset(column_names)


def test_role_foreign_key_and_unique_constraint() -> None:
    """Verifies guild_id foreign key references guilds.id and (guild_id, discord_role_id) is unique."""
    table = Base.metadata.tables["roles"]

    # Check foreign key
    fk_targets = {fk.target_fullname for fk in table.foreign_keys}
    assert "guilds.id" in fk_targets

    # Check unique constraint on (guild_id, discord_role_id)
    unique_constraints = [
        c for c in table.constraints if hasattr(c, "columns") and len(c.columns) == 2
    ]
    has_role_unique = any(
        {"guild_id", "discord_role_id"} == {col.name for col in uq.columns}
        for uq in unique_constraints
    )
    assert has_role_unique is True


@pytest.mark.asyncio
async def test_get_role_query() -> None:
    """Verifies get_role executes expected query and returns matching record."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    guild_id = uuid.uuid4()
    existing_role = Role(guild_id=guild_id, discord_role_id=123456789, name="Admin", position=1)
    mock_result.scalar_one_or_none.return_value = existing_role
    mock_session.execute.return_value = mock_result

    role = await get_role(mock_session, guild_id, 123456789)

    assert role is existing_role
    mock_session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_or_create_role_creates_new() -> None:
    """Verifies get_or_create_role creates and persists a new Role when non-existent."""
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
    role, created = await get_or_create_role(
        session=mock_session,
        guild_id=guild_id,
        discord_role_id=123456789,
        name="Moderator",
        position=5,
    )

    assert created is True
    assert role.guild_id == guild_id
    assert role.discord_role_id == 123456789
    assert role.name == "Moderator"
    assert role.position == 5
    mock_session.add.assert_called_once_with(role)
    mock_session.flush.assert_awaited_once()
    mock_session.begin_nested.assert_called_once()


@pytest.mark.asyncio
async def test_get_or_create_role_returns_existing_unchanged() -> None:
    """Verifies existing Role with unchanged name and position is returned with created=False."""
    mock_session = AsyncMock()
    guild_id = uuid.uuid4()
    existing = Role(
        guild_id=guild_id,
        discord_role_id=123456789,
        name="Member",
        position=10,
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing
    mock_session.execute.return_value = mock_result

    role, created = await get_or_create_role(
        session=mock_session,
        guild_id=guild_id,
        discord_role_id=123456789,
        name="Member",
        position=10,
    )

    assert created is False
    assert role == existing
    mock_session.add.assert_not_called()
    mock_session.flush.assert_not_called()


@pytest.mark.asyncio
async def test_get_or_create_role_updates_name_when_changed() -> None:
    """Verifies existing role name is updated and flushed when Discord role name changes."""
    mock_session = AsyncMock()
    guild_id = uuid.uuid4()
    existing = Role(
        guild_id=guild_id,
        discord_role_id=123456789,
        name="Old Name",
        position=5,
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing
    mock_session.execute.return_value = mock_result
    mock_session.flush = AsyncMock()

    role, created = await get_or_create_role(
        session=mock_session,
        guild_id=guild_id,
        discord_role_id=123456789,
        name="New Name",
        position=5,
    )

    assert created is False
    assert role.name == "New Name"
    mock_session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_or_create_role_updates_position_when_changed() -> None:
    """Verifies existing role position is updated and flushed when position changes."""
    mock_session = AsyncMock()
    guild_id = uuid.uuid4()
    existing = Role(
        guild_id=guild_id,
        discord_role_id=123456789,
        name="VIP",
        position=2,
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing
    mock_session.execute.return_value = mock_result
    mock_session.flush = AsyncMock()

    role, created = await get_or_create_role(
        session=mock_session,
        guild_id=guild_id,
        discord_role_id=123456789,
        name="VIP",
        position=8,
    )

    assert created is False
    assert role.position == 8
    mock_session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_or_create_role_recovers_from_race_condition() -> None:
    """Verifies IntegrityError during nested savepoint insertion recovers safely by re-querying."""
    mock_session = MagicMock()
    guild_id = uuid.uuid4()

    concurrent_role = Role(
        guild_id=guild_id,
        discord_role_id=123456789,
        name="Concurrent Role",
        position=3,
    )
    mock_result_1 = MagicMock()
    mock_result_1.scalar_one_or_none.return_value = None

    mock_result_2 = MagicMock()
    mock_result_2.scalar_one_or_none.return_value = concurrent_role

    mock_session.execute = AsyncMock(side_effect=[mock_result_1, mock_result_2])
    mock_session.flush = AsyncMock(side_effect=[IntegrityError("duplicate key", params=None, orig=Exception()), None])

    mock_nested_cm = MagicMock()
    mock_nested_cm.__aenter__ = AsyncMock(return_value=mock_nested_cm)
    mock_nested_cm.__aexit__ = AsyncMock(return_value=False)
    mock_session.begin_nested.return_value = mock_nested_cm

    role, created = await get_or_create_role(
        session=mock_session,
        guild_id=guild_id,
        discord_role_id=123456789,
        name="Concurrent Role",
        position=3,
    )

    assert created is False
    assert role == concurrent_role
    mock_session.begin_nested.assert_called_once()
    assert mock_session.execute.await_count == 2


@pytest.mark.asyncio
async def test_delete_role() -> None:
    """Verifies delete_role deletes matching role record and calls session.delete and session.flush."""
    mock_session = AsyncMock()
    guild_id = uuid.uuid4()
    existing_role = Role(guild_id=guild_id, discord_role_id=123456789, name="Deleted Role", position=1)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_role
    mock_session.execute.return_value = mock_result

    deleted = await delete_role(mock_session, guild_id, 123456789)

    assert deleted is True
    mock_session.delete.assert_called_once_with(existing_role)
    mock_session.flush.assert_awaited_once()
