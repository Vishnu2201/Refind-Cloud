"""Database operations service for managing Support Tickets."""

import datetime
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tickets.models import Ticket, TicketStatus

logger = logging.getLogger(__name__)


async def create_ticket(
    session: AsyncSession,
    guild_id: uuid.UUID,
    user_id: uuid.UUID,
    subject: str,
) -> Ticket:
    """Creates and persists a new support ticket with status OPEN."""
    new_ticket = Ticket(
        guild_id=guild_id,
        user_id=user_id,
        subject=subject,
        status=TicketStatus.OPEN,
        discord_channel_id=None,
        closed_at=None,
    )
    session.add(new_ticket)
    await session.flush()
    return new_ticket


async def get_ticket(
    session: AsyncSession,
    ticket_id: uuid.UUID,
) -> Ticket | None:
    """Retrieves a Ticket record by its internal UUID primary key."""
    stmt = select(Ticket).where(Ticket.id == ticket_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_ticket_by_discord_channel_id(
    session: AsyncSession,
    discord_channel_id: int,
) -> Ticket | None:
    """Retrieves a Ticket record by its associated Discord channel ID."""
    stmt = select(Ticket).where(Ticket.discord_channel_id == discord_channel_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def set_ticket_discord_channel(
    session: AsyncSession,
    ticket_id: uuid.UUID,
    discord_channel_id: int,
) -> Ticket | None:
    """Associates a Discord channel ID with an existing ticket."""
    ticket = await get_ticket(session, ticket_id)
    if ticket is None:
        return None

    if ticket.discord_channel_id != discord_channel_id:
        ticket.discord_channel_id = discord_channel_id
        await session.flush()

    return ticket


async def close_ticket(
    session: AsyncSession,
    ticket_id: uuid.UUID,
) -> Ticket | None:
    """Closes a ticket by updating its status to CLOSED and setting closed_at timestamp."""
    ticket = await get_ticket(session, ticket_id)
    if ticket is None:
        return None

    if ticket.status != TicketStatus.CLOSED:
        ticket.status = TicketStatus.CLOSED
        ticket.closed_at = datetime.datetime.now(datetime.timezone.utc)
        await session.flush()

    return ticket


async def get_open_ticket_for_user(
    session: AsyncSession,
    guild_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Ticket | None:
    """Retrieves an active open ticket for a user in a specific guild, if one exists."""
    stmt = select(Ticket).where(
        Ticket.guild_id == guild_id,
        Ticket.user_id == user_id,
        Ticket.status == TicketStatus.OPEN,
    )
    result = await session.execute(stmt)
    return result.scalars().first()
