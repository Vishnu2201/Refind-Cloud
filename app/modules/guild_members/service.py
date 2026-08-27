"""Database operations service for managing Discord Guild Members."""

import datetime
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.guild_members.models import GuildMember

logger = logging.getLogger(__name__)


async def get_guild_member(
    session: AsyncSession,
    guild_id: uuid.UUID,
    user_id: uuid.UUID,
) -> GuildMember | None:
    """Retrieves a GuildMember relationship record by its unique guild_id and user_id."""
    stmt = select(GuildMember).where(
        GuildMember.guild_id == guild_id,
        GuildMember.user_id == user_id,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_or_create_guild_member(
    session: AsyncSession,
    guild_id: uuid.UUID,
    user_id: uuid.UUID,
    joined_at: datetime.datetime | None = None,
) -> tuple[GuildMember, bool]:
    """Retrieves an existing GuildMember relationship or creates and persists a new one.

    Uses a nested transaction (SAVEPOINT) during creation so that unique constraint
    race conditions roll back only the savepoint without invalidating the outer transaction.

    Returns:
        tuple[GuildMember, bool]: A tuple containing the GuildMember instance and a boolean
                                  flag indicating whether the record was newly created (True)
                                  or pre-existing (False).
    """
    existing_member = await get_guild_member(session, guild_id, user_id)
    if existing_member is not None:
        if joined_at is not None and existing_member.joined_at != joined_at:
            existing_member.joined_at = joined_at
            await session.flush()
        return existing_member, False

    # Attempt creation using a nested transaction (SAVEPOINT)
    try:
        async with session.begin_nested():
            new_member = GuildMember(
                guild_id=guild_id,
                user_id=user_id,
                joined_at=joined_at,
            )
            session.add(new_member)
            await session.flush()
        return new_member, True
    except IntegrityError:
        # Savepoint was automatically rolled back by begin_nested().
        # Outer transaction remains healthy. Re-query for the concurrently created record.
        existing_member = await get_guild_member(session, guild_id, user_id)
        if existing_member is not None:
            if joined_at is not None and existing_member.joined_at != joined_at:
                existing_member.joined_at = joined_at
                await session.flush()
            return existing_member, False
        raise
