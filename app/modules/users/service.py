"""Database operations service for managing Discord User Identities."""

import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User

logger = logging.getLogger(__name__)


async def get_user_by_discord_id(
    session: AsyncSession,
    discord_user_id: int,
) -> User | None:
    """Retrieves a User identity record by its unique Discord user ID."""
    stmt = select(User).where(User.discord_user_id == discord_user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_or_create_user(
    session: AsyncSession,
    discord_user_id: int,
    username: str,
    global_name: str | None = None,
) -> tuple[User, bool]:
    """Retrieves an existing User or creates and persists a new User identity.

    Returns:
        tuple[User, bool]: A tuple containing the User instance and a boolean flag
                           indicating whether the profile was newly created (True)
                           or pre-existing (False).
    """
    existing_user = await get_user_by_discord_id(session, discord_user_id)
    if existing_user is not None:
        # Update username or global_name if modified in Discord
        updated = False
        if existing_user.username != username:
            existing_user.username = username
            updated = True
        if existing_user.global_name != global_name:
            existing_user.global_name = global_name
            updated = True

        if updated:
            await session.flush()

        return existing_user, False

    # Instantiate new User
    new_user = User(
        discord_user_id=discord_user_id,
        username=username,
        global_name=global_name,
    )
    session.add(new_user)

    try:
        await session.flush()
        return new_user, True
    except IntegrityError:
        # Safety fallback for concurrent user creation race conditions
        await session.rollback()
        existing_user = await get_user_by_discord_id(session, discord_user_id)
        if existing_user is not None:
            return existing_user, False
        raise
