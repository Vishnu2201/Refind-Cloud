"""Database operations service for managing Discord Roles."""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.roles.models import Role

logger = logging.getLogger(__name__)


async def get_role(
    session: AsyncSession,
    guild_id: uuid.UUID,
    discord_role_id: int,
) -> Role | None:
    """Retrieves a Role record by its internal guild_id and unique Discord role ID."""
    stmt = select(Role).where(
        Role.guild_id == guild_id,
        Role.discord_role_id == discord_role_id,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_or_create_role(
    session: AsyncSession,
    guild_id: uuid.UUID,
    discord_role_id: int,
    name: str,
    position: int,
) -> tuple[Role, bool]:
    """Retrieves an existing Role or creates and persists a new Role record.

    Uses a nested transaction (SAVEPOINT) during creation so that unique constraint
    race conditions roll back only the savepoint without invalidating the outer transaction.

    Returns:
        tuple[Role, bool]: A tuple containing the Role instance and a boolean flag
                           indicating whether the record was newly created (True)
                           or pre-existing (False).
    """
    existing_role = await get_role(session, guild_id, discord_role_id)
    if existing_role is not None:
        updated = False
        if existing_role.name != name:
            existing_role.name = name
            updated = True
        if existing_role.position != position:
            existing_role.position = position
            updated = True

        if updated:
            await session.flush()

        return existing_role, False

    # Attempt creation using a nested transaction (SAVEPOINT)
    try:
        async with session.begin_nested():
            new_role = Role(
                guild_id=guild_id,
                discord_role_id=discord_role_id,
                name=name,
                position=position,
            )
            session.add(new_role)
            await session.flush()
        return new_role, True
    except IntegrityError:
        # Savepoint was automatically rolled back by begin_nested().
        # Outer transaction remains healthy. Re-query for the concurrently created record.
        existing_role = await get_role(session, guild_id, discord_role_id)
        if existing_role is not None:
            updated = False
            if existing_role.name != name:
                existing_role.name = name
                updated = True
            if existing_role.position != position:
                existing_role.position = position
                updated = True

            if updated:
                await session.flush()

            return existing_role, False
        raise


async def delete_role(
    session: AsyncSession,
    guild_id: uuid.UUID,
    discord_role_id: int,
) -> bool:
    """Deletes a Role record matching internal guild_id and Discord role ID.

    Returns:
        bool: True if the role record was found and deleted, False otherwise.
    """
    role = await get_role(session, guild_id, discord_role_id)
    if role is not None:
        await session.delete(role)
        await session.flush()
        return True
    return False
