"""Database operations service for managing Discord Guilds."""

import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.guilds.models import Guild

logger = logging.getLogger(__name__)


async def get_guild_by_discord_id(
    session: AsyncSession,
    discord_guild_id: int,
) -> Guild | None:
    """Retrieves a Guild record by its unique Discord guild ID."""
    stmt = select(Guild).where(Guild.discord_guild_id == discord_guild_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_or_create_guild(
    session: AsyncSession,
    discord_guild_id: int,
    name: str,
) -> tuple[Guild, bool]:
    """Retrieves an existing Guild or creates and persists a new Guild record.

    Uses a nested transaction (SAVEPOINT) during creation so that unique constraint
    race conditions roll back only the savepoint without invalidating the outer transaction.

    Returns:
        tuple[Guild, bool]: A tuple containing the Guild instance and a boolean flag
                           indicating whether the record was newly created (True)
                           or pre-existing (False).
    """
    existing_guild = await get_guild_by_discord_id(session, discord_guild_id)
    if existing_guild is not None:
        if existing_guild.name != name:
            existing_guild.name = name
            await session.flush()
        return existing_guild, False

    # Attempt creation using a nested transaction (SAVEPOINT)
    try:
        async with session.begin_nested():
            new_guild = Guild(
                discord_guild_id=discord_guild_id,
                name=name,
            )
            session.add(new_guild)
            await session.flush()
        return new_guild, True
    except IntegrityError:
        # Savepoint was automatically rolled back by begin_nested().
        # Outer transaction remains healthy. Re-query for the concurrently created record.
        existing_guild = await get_guild_by_discord_id(session, discord_guild_id)
        if existing_guild is not None:
            if existing_guild.name != name:
                existing_guild.name = name
                await session.flush()
            return existing_guild, False
        raise
