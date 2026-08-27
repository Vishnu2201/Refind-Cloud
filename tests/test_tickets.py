"""Unit tests for Support Ticket model and service logic."""

from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from app.database.base import Base
from app.modules.tickets.models import Ticket, TicketStatus
from app.modules.tickets.service import (
    close_ticket,
    create_ticket,
    get_open_ticket_for_user,
    get_ticket,
    get_ticket_by_discord_channel_id,
    set_ticket_discord_channel,
)


def test_tickets_model_metadata_registered() -> None:
    """Verifies that the Ticket model is registered in Base.metadata under 'tickets'."""
    assert "tickets" in Base.metadata.tables
    table = Base.metadata.tables["tickets"]

    column_names = {col.name for col in table.columns}
    expected_columns = {
        "id",
        "guild_id",
        "user_id",
        "discord_channel_id",
        "status",
        "subject",
        "created_at",
        "updated_at",
        "closed_at",
    }
    assert expected_columns.issubset(column_names)


def test_tickets_guild_id_foreign_key() -> None:
    """Verifies guild_id foreign key points to guilds.id with ON DELETE CASCADE."""
    table = Base.metadata.tables["tickets"]

    guild_fks = [fk for fk in table.foreign_keys if fk.target_fullname == "guilds.id"]
    assert len(guild_fks) == 1
    assert guild_fks[0].ondelete == "CASCADE"


def test_tickets_user_id_foreign_key() -> None:
    """Verifies user_id foreign key points to users.id with ON DELETE CASCADE."""
    table = Base.metadata.tables["tickets"]

    user_fks = [fk for fk in table.foreign_keys if fk.target_fullname == "users.id"]
    assert len(user_fks) == 1
    assert user_fks[0].ondelete == "CASCADE"


def test_tickets_discord_channel_id_unique_index() -> None:
    """Verifies discord_channel_id column has unique=True and is indexed."""
    table = Base.metadata.tables["tickets"]
    col = table.columns["discord_channel_id"]

    assert col.unique is True
    assert col.index is True


def test_tickets_status_default_configuration() -> None:
    """Verifies status default configuration is TicketStatus.OPEN."""
    table = Base.metadata.tables["tickets"]
    col = table.columns["status"]

    assert col.default.arg == TicketStatus.OPEN
    assert col.server_default.arg == "open"


@pytest.mark.asyncio
async def test_create_ticket() -> None:
    """Verifies create_ticket creates a ticket with OPEN status and flushes session."""
    mock_session = AsyncMock()
    guild_id = uuid.uuid4()
    user_id = uuid.uuid4()
    subject = "Need help with roles"

    ticket = await create_ticket(mock_session, guild_id, user_id, subject)

    assert ticket.guild_id == guild_id
    assert ticket.user_id == user_id
    assert ticket.subject == subject
    assert ticket.status == TicketStatus.OPEN
    assert ticket.discord_channel_id is None
    assert ticket.closed_at is None

    mock_session.add.assert_called_once_with(ticket)
    mock_session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_ticket() -> None:
    """Verifies get_ticket executes expected query with ticket_id."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    ticket_id = uuid.uuid4()

    mock_ticket = Ticket(id=ticket_id, guild_id=uuid.uuid4(), user_id=uuid.uuid4(), subject="Test")
    mock_result.scalar_one_or_none.return_value = mock_ticket
    mock_session.execute.return_value = mock_result

    ticket = await get_ticket(mock_session, ticket_id)

    assert ticket is mock_ticket
    mock_session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_ticket_by_discord_channel_id() -> None:
    """Verifies get_ticket_by_discord_channel_id executes query with channel ID."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    discord_channel_id = 987654321012345678

    mock_ticket = Ticket(
        id=uuid.uuid4(),
        guild_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        subject="Channel Test",
        discord_channel_id=discord_channel_id,
    )
    mock_result.scalar_one_or_none.return_value = mock_ticket
    mock_session.execute.return_value = mock_result

    ticket = await get_ticket_by_discord_channel_id(mock_session, discord_channel_id)

    assert ticket is mock_ticket
    mock_session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_ticket_discord_channel() -> None:
    """Verifies set_ticket_discord_channel updates channel ID and flushes session."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    ticket_id = uuid.uuid4()
    discord_channel_id = 112233445566778899

    mock_ticket = Ticket(id=ticket_id, guild_id=uuid.uuid4(), user_id=uuid.uuid4(), subject="Channel Link")
    mock_result.scalar_one_or_none.return_value = mock_ticket
    mock_session.execute.return_value = mock_result

    updated_ticket = await set_ticket_discord_channel(mock_session, ticket_id, discord_channel_id)

    assert updated_ticket is mock_ticket
    assert updated_ticket.discord_channel_id == discord_channel_id
    mock_session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_close_ticket() -> None:
    """Verifies close_ticket updates status to CLOSED and sets closed_at timestamp."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    ticket_id = uuid.uuid4()

    mock_ticket = Ticket(
        id=ticket_id,
        guild_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        subject="Close Test",
        status=TicketStatus.OPEN,
    )
    mock_result.scalar_one_or_none.return_value = mock_ticket
    mock_session.execute.return_value = mock_result

    closed = await close_ticket(mock_session, ticket_id)

    assert closed is mock_ticket
    assert closed.status == TicketStatus.CLOSED
    assert closed.closed_at is not None
    mock_session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_close_ticket_idempotent() -> None:
    """Verifies close_ticket is safe to call on an already closed ticket without extra flush."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    ticket_id = uuid.uuid4()

    mock_ticket = Ticket(
        id=ticket_id,
        guild_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        subject="Already Closed",
        status=TicketStatus.CLOSED,
    )
    mock_result.scalar_one_or_none.return_value = mock_ticket
    mock_session.execute.return_value = mock_result

    closed = await close_ticket(mock_session, ticket_id)

    assert closed is mock_ticket
    assert closed.status == TicketStatus.CLOSED
    mock_session.flush.assert_not_called()


@pytest.mark.asyncio
async def test_get_open_ticket_for_user() -> None:
    """Verifies get_open_ticket_for_user queries open tickets for specific guild and user."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_scalars = MagicMock()

    guild_id = uuid.uuid4()
    user_id = uuid.uuid4()

    open_ticket = Ticket(
        id=uuid.uuid4(),
        guild_id=guild_id,
        user_id=user_id,
        subject="Open Ticket",
        status=TicketStatus.OPEN,
    )
    mock_scalars.first.return_value = open_ticket
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute.return_value = mock_result

    ticket = await get_open_ticket_for_user(mock_session, guild_id, user_id)

    assert ticket is open_ticket
    mock_session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_open_ticket_for_user_none() -> None:
    """Verifies get_open_ticket_for_user handles no active ticket safely."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_scalars = MagicMock()

    guild_id = uuid.uuid4()
    user_id = uuid.uuid4()

    mock_scalars.first.return_value = None
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute.return_value = mock_result

    ticket = await get_open_ticket_for_user(mock_session, guild_id, user_id)

    assert ticket is None
    mock_session.execute.assert_awaited_once()
