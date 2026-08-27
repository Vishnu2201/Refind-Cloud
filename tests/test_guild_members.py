"""Unit tests for Discord GuildMember relationship model and service logic."""

import datetime
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.database.base import Base
from app.modules.guild_members.models import GuildMember
from app.modules.guild_members.service import get_guild_member, get_or_create_guild_member


def test_guild_member_model_metadata_registered() -> None:
    """Verifies that the GuildMember model is registered in Base.metadata under 'guild_members'."""
    assert "guild_members" in Base.metadata.tables
    table = Base.metadata.tables["guild_members"]

    column_names = {col.name for col in table.columns}
    expected_columns = {"id", "guild_id", "user_id", "joined_at", "created_at", "updated_at"}
    assert expected_columns.issubset(column_names)


def test_guild_member_foreign_keys_and_unique_constraint() -> None:
    """Verifies foreign key targets and (guild_id, user_id) unique constraint on GuildMember model."""
    table = Base.metadata.tables["guild_members"]

    # Check foreign keys
    fk_targets = {fk.target_fullname for fk in table.foreign_keys}
    assert "guilds.id" in fk_targets
    assert "users.id" in fk_targets

    # Check unique constraint on (guild_id, user_id)
    unique_constraints = [
        c for c in table.constraints if hasattr(c, "columns") and len(c.columns) == 2
    ]
    has_guild_user_unique = any(
        {"guild_id", "user_id"} == {col.name for col in uq.columns}
        for uq in unique_constraints
    )
    assert has_guild_user_unique is True


@pytest.mark.asyncio
async def test_get_guild_member_query() -> None:
    """Verifies get_guild_member executes expected query and returns matching member."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    guild_id = uuid.uuid4()
    user_id = uuid.uuid4()
    existing_member = GuildMember(guild_id=guild_id, user_id=user_id)
    mock_result.scalar_one_or_none.return_value = existing_member
    mock_session.execute.return_value = mock_result

    member = await get_guild_member(mock_session, guild_id, user_id)

    assert member is existing_member
    mock_session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_or_create_guild_member_creates_new() -> None:
    """Verifies get_or_create_guild_member creates and persists a new GuildMember when non-existent."""
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
    user_id = uuid.uuid4()
    now = datetime.datetime.now(datetime.timezone.utc)

    member, created = await get_or_create_guild_member(
        session=mock_session,
        guild_id=guild_id,
        user_id=user_id,
        joined_at=now,
    )

    assert created is True
    assert member.guild_id == guild_id
    assert member.user_id == user_id
    assert member.joined_at == now
    mock_session.add.assert_called_once_with(member)
    mock_session.flush.assert_awaited_once()
    mock_session.begin_nested.assert_called_once()


@pytest.mark.asyncio
async def test_get_or_create_guild_member_returns_existing_unchanged() -> None:
    """Verifies existing GuildMember with unchanged joined_at is returned without unnecessary flush calls."""
    mock_session = AsyncMock()
    guild_id = uuid.uuid4()
    user_id = uuid.uuid4()
    now = datetime.datetime.now(datetime.timezone.utc)

    existing = GuildMember(guild_id=guild_id, user_id=user_id, joined_at=now)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing
    mock_session.execute.return_value = mock_result

    member, created = await get_or_create_guild_member(
        session=mock_session,
        guild_id=guild_id,
        user_id=user_id,
        joined_at=now,
    )

    assert created is False
    assert member == existing
    mock_session.add.assert_not_called()
    mock_session.flush.assert_not_called()


@pytest.mark.asyncio
async def test_get_or_create_guild_member_updates_joined_at() -> None:
    """Verifies existing GuildMember joined_at is updated and flushed when changed."""
    mock_session = AsyncMock()
    guild_id = uuid.uuid4()
    user_id = uuid.uuid4()
    old_time = datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc)
    new_time = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)

    existing = GuildMember(guild_id=guild_id, user_id=user_id, joined_at=old_time)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing
    mock_session.execute.return_value = mock_result

    member, created = await get_or_create_guild_member(
        session=mock_session,
        guild_id=guild_id,
        user_id=user_id,
        joined_at=new_time,
    )

    assert created is False
    assert member.joined_at == new_time
    mock_session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_or_create_guild_member_recovers_from_race_condition() -> None:
    """Verifies IntegrityError during nested savepoint insertion recovers safely by re-querying."""
    mock_session = MagicMock()
    guild_id = uuid.uuid4()
    user_id = uuid.uuid4()

    concurrent_member = GuildMember(guild_id=guild_id, user_id=user_id)
    mock_result_1 = MagicMock()
    mock_result_1.scalar_one_or_none.return_value = None

    mock_result_2 = MagicMock()
    mock_result_2.scalar_one_or_none.return_value = concurrent_member

    mock_session.execute = AsyncMock(side_effect=[mock_result_1, mock_result_2])
    mock_session.flush = AsyncMock(side_effect=[IntegrityError("duplicate key", params=None, orig=Exception()), None])

    mock_nested_cm = MagicMock()
    mock_nested_cm.__aenter__ = AsyncMock(return_value=mock_nested_cm)
    mock_nested_cm.__aexit__ = AsyncMock(return_value=False)
    mock_session.begin_nested.return_value = mock_nested_cm

    member, created = await get_or_create_guild_member(
        session=mock_session,
        guild_id=guild_id,
        user_id=user_id,
    )

    assert created is False
    assert member == concurrent_member
    mock_session.begin_nested.assert_called_once()
    assert mock_session.execute.await_count == 2
