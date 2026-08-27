"""Unit tests for Discord GuildMemberRole relationship model and service logic."""

from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from app.database.base import Base
from app.modules.guild_member_roles.models import GuildMemberRole
from app.modules.guild_member_roles.service import (
    assign_guild_member_role,
    get_guild_member_role,
    remove_guild_member_role,
)


def test_guild_member_role_model_metadata_registered() -> None:
    """Verifies that the GuildMemberRole model is registered in Base.metadata under 'guild_member_roles'."""
    assert "guild_member_roles" in Base.metadata.tables
    table = Base.metadata.tables["guild_member_roles"]

    column_names = {col.name for col in table.columns}
    expected_columns = {"id", "guild_member_id", "role_id", "created_at", "updated_at"}
    assert expected_columns.issubset(column_names)


def test_guild_member_role_foreign_keys() -> None:
    """Verifies foreign key targets and cascade configuration for guild_member_id and role_id."""
    table = Base.metadata.tables["guild_member_roles"]

    fk_targets = {fk.target_fullname for fk in table.foreign_keys}
    assert "guild_members.id" in fk_targets
    assert "roles.id" in fk_targets

    # Check ondelete="CASCADE" configuration
    for fk in table.foreign_keys:
        assert fk.ondelete == "CASCADE"


def test_guild_member_role_unique_constraint() -> None:
    """Verifies unique constraint exists on (guild_member_id, role_id) with expected constraint name."""
    table = Base.metadata.tables["guild_member_roles"]

    unique_constraints = [
        c for c in table.constraints if getattr(c, "name", None) == "uq_guild_member_roles_member_role"
    ]
    assert len(unique_constraints) == 1

    uq = unique_constraints[0]
    column_names = {col.name for col in uq.columns}
    assert column_names == {"guild_member_id", "role_id"}


@pytest.mark.asyncio
async def test_get_guild_member_role_query() -> None:
    """Verifies get_guild_member_role executes expected query with guild_member_id and role_id."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    guild_member_id = uuid.uuid4()
    role_id = uuid.uuid4()

    existing_gmr = GuildMemberRole(guild_member_id=guild_member_id, role_id=role_id)
    mock_result.scalar_one_or_none.return_value = existing_gmr
    mock_session.execute.return_value = mock_result

    gmr = await get_guild_member_role(mock_session, guild_member_id, role_id)

    assert gmr is existing_gmr
    mock_session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_assign_guild_member_role_creates_new() -> None:
    """Verifies assign_guild_member_role executes conflict-safe insert and returns created=True when new."""
    mock_session = AsyncMock()
    guild_member_id = uuid.uuid4()
    role_id = uuid.uuid4()

    new_gmr = GuildMemberRole(guild_member_id=guild_member_id, role_id=role_id)

    mock_insert_result = MagicMock()
    mock_insert_result.rowcount = 1

    mock_select_result = MagicMock()
    mock_select_result.scalar_one_or_none.return_value = new_gmr

    mock_session.execute.side_effect = [mock_insert_result, mock_select_result]

    gmr, created = await assign_guild_member_role(
        session=mock_session,
        guild_member_id=guild_member_id,
        role_id=role_id,
    )

    assert created is True
    assert gmr == new_gmr
    assert mock_session.execute.await_count == 2


@pytest.mark.asyncio
async def test_assign_guild_member_role_returns_existing_duplicate() -> None:
    """Verifies assign_guild_member_role returns existing relationship with created=False when conflict occurs."""
    mock_session = AsyncMock()
    guild_member_id = uuid.uuid4()
    role_id = uuid.uuid4()

    existing_gmr = GuildMemberRole(guild_member_id=guild_member_id, role_id=role_id)

    mock_insert_result = MagicMock()
    mock_insert_result.rowcount = 0

    mock_select_result = MagicMock()
    mock_select_result.scalar_one_or_none.return_value = existing_gmr

    mock_session.execute.side_effect = [mock_insert_result, mock_select_result]

    gmr, created = await assign_guild_member_role(
        session=mock_session,
        guild_member_id=guild_member_id,
        role_id=role_id,
    )

    assert created is False
    assert gmr == existing_gmr
    assert mock_session.execute.await_count == 2


@pytest.mark.asyncio
async def test_remove_guild_member_role_deletes_existing() -> None:
    """Verifies remove_guild_member_role executes delete query and returns True when a row was deleted."""
    mock_session = AsyncMock()
    guild_member_id = uuid.uuid4()
    role_id = uuid.uuid4()

    mock_result = MagicMock()
    mock_result.rowcount = 1
    mock_session.execute.return_value = mock_result

    removed = await remove_guild_member_role(mock_session, guild_member_id, role_id)

    assert removed is True
    mock_session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_remove_guild_member_role_handles_missing_safely() -> None:
    """Verifies remove_guild_member_role returns False when no matching row was found to delete."""
    mock_session = AsyncMock()
    guild_member_id = uuid.uuid4()
    role_id = uuid.uuid4()

    mock_result = MagicMock()
    mock_result.rowcount = 0
    mock_session.execute.return_value = mock_result

    removed = await remove_guild_member_role(mock_session, guild_member_id, role_id)

    assert removed is False
    mock_session.execute.assert_awaited_once()
