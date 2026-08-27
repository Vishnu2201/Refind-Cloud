"""Custom Discord bot client managing async lifecycle hooks and command synchronization."""

import logging

import discord
from discord.ext import commands

from app.core.context import get_app_context
from app.database.session import check_database_health, close_db_engine, get_session_factory, init_db_resources
from app.modules.guild_member_roles.service import assign_guild_member_role, remove_guild_member_role
from app.modules.guild_members.service import get_or_create_guild_member
from app.modules.guild_settings.service import get_or_create_guild_settings
from app.modules.guilds.service import get_guild_by_discord_id, get_or_create_guild
from app.modules.roles.service import delete_role, get_or_create_role, get_role
from app.modules.users.service import get_or_create_user

logger = logging.getLogger(__name__)


class RefindCloudBot(commands.Bot):
    """Refind Cloud production Discord bot client."""

    def __init__(self, guild_id: int | None = None) -> None:
        # Minimum required intents for foundation slash command functionality
        intents = discord.Intents.default()

        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            help_command=None,
        )
        self.guild_id = guild_id

    async def sync_application_commands(self) -> list[discord.app_commands.AppCommand]:
        """Synchronizes application slash commands globally or to a specific development guild.

        Returns:
            list[discord.app_commands.AppCommand]: List of synchronized application commands.
        """
        if self.guild_id:
            guild_target = discord.Object(id=self.guild_id)
            self.tree.copy_global_to(guild=guild_target)
            synced = await self.tree.sync(guild=guild_target)
            logger.info(
                f"Successfully synced {len(synced)} slash command(s) instantly to Guild ID: {self.guild_id}"
            )
            return synced
        else:
            synced = await self.tree.sync()
            logger.info(
                f"Successfully synced {len(synced)} global slash command(s)."
            )
            return synced

    async def register_connected_guilds(self) -> None:
        """Persists connected Discord guilds, settings, roles, members, and role assignments on startup."""
        if not self.guilds:
            return

        session_factory = get_session_factory()
        async with session_factory() as session:
            async with session.begin():
                for guild in self.guilds:
                    db_guild, _ = await get_or_create_guild(
                        session=session,
                        discord_guild_id=guild.id,
                        name=guild.name,
                    )
                    await get_or_create_guild_settings(
                        session=session,
                        guild_id=db_guild.id,
                    )
                    db_roles_map = {}
                    for role in guild.roles:
                        if role.is_default() or role.name == "@everyone":
                            continue
                        db_role, _ = await get_or_create_role(
                            session=session,
                            guild_id=db_guild.id,
                            discord_role_id=role.id,
                            name=role.name,
                            position=role.position,
                        )
                        db_roles_map[role.id] = db_role

                    for member in guild.members:
                        db_user, _ = await get_or_create_user(
                            session=session,
                            discord_user_id=member.id,
                            username=member.name,
                            global_name=member.global_name or member.display_name,
                        )
                        db_member, _ = await get_or_create_guild_member(
                            session=session,
                            guild_id=db_guild.id,
                            user_id=db_user.id,
                            joined_at=member.joined_at,
                        )
                        for role in member.roles:
                            if role.is_default() or role.name == "@everyone":
                                continue
                            db_role = db_roles_map.get(role.id)
                            if db_role is None:
                                db_role, _ = await get_or_create_role(
                                    session=session,
                                    guild_id=db_guild.id,
                                    discord_role_id=role.id,
                                    name=role.name,
                                    position=role.position,
                                )
                                db_roles_map[role.id] = db_role

                            await assign_guild_member_role(
                                session=session,
                                guild_member_id=db_member.id,
                                role_id=db_role.id,
                            )
        logger.info(
            f"Registered {len(self.guilds)} connected Discord guild(s), settings, roles, and members in database."
        )

    async def setup_hook(self) -> None:
        """Asynchronous setup hook executed prior to Discord connection establishment."""
        logger.info("Initializing database resources inside Discord event loop...")
        ctx = get_app_context()

        db_engine, session_factory = init_db_resources(
            database_url=ctx.settings.database_url_str,
            echo=(ctx.settings.ENVIRONMENT == "development" and ctx.settings.LOG_LEVEL.upper() == "DEBUG"),
        )
        ctx.db_engine = db_engine
        ctx.session_factory = session_factory

        logger.info("Executing mandatory PostgreSQL connectivity check (SELECT 1)...")
        is_healthy = await check_database_health(db_engine)
        if not is_healthy:
            logger.critical(
                "CRITICAL: Required PostgreSQL database infrastructure is unavailable. "
                "Aborting bot startup sequence. Disposing database resources..."
            )
            await close_db_engine(db_engine)
            raise RuntimeError("PostgreSQL database infrastructure health check failed during bot setup.")

        logger.info("Database health check PASSED: PostgreSQL connection verified.")

        logger.info("Loading foundational cogs...")
        await self.load_extension("app.bot.cogs.ping")
        logger.info("Successfully registered cog: app.bot.cogs.ping")
        await self.load_extension("app.bot.cogs.user")
        logger.info("Successfully registered cog: app.bot.cogs.user")

        # Synchronize slash commands using dedicated reusable method
        await self.sync_application_commands()

    async def on_ready(self) -> None:
        """Event fired when Discord bot successfully connects and authenticates."""
        user_str = str(self.user) if self.user else "Unknown"
        user_id = self.user.id if self.user else 0
        latency_ms = round(self.latency * 1000)

        logger.info(f"Bot connected successfully as {user_str} (ID: {user_id})")
        logger.info(f"Initial websocket latency: {latency_ms}ms")
        logger.info(f"Connected to {len(self.guilds)} Discord guild(s).")

        # Persist connected guilds, settings, roles, and cached members into database
        try:
            await self.register_connected_guilds()
        except Exception as exc:
            logger.error(f"Error registering connected guilds on startup: {exc}")

    async def on_guild_join(self, guild: discord.Guild) -> None:
        """Event fired when the bot joins a new Discord guild."""
        logger.info(f"Joined new Discord guild: {guild.name} (ID: {guild.id})")
        try:
            session_factory = get_session_factory()
            async with session_factory() as session:
                async with session.begin():
                    db_guild, _ = await get_or_create_guild(
                        session=session,
                        discord_guild_id=guild.id,
                        name=guild.name,
                    )
                    await get_or_create_guild_settings(
                        session=session,
                        guild_id=db_guild.id,
                    )
                    for role in guild.roles:
                        if role.is_default() or role.name == "@everyone":
                            continue
                        await get_or_create_role(
                            session=session,
                            guild_id=db_guild.id,
                            discord_role_id=role.id,
                            name=role.name,
                            position=role.position,
                        )
        except Exception as exc:
            logger.error(f"Error registering newly joined guild {guild.id}: {exc}")

    async def on_member_join(self, member: discord.Member) -> None:
        """Event fired when a member joins a Discord guild."""
        logger.info(
            f"Member {member} (ID: {member.id}) joined guild {member.guild.name} (ID: {member.guild.id})"
        )
        try:
            session_factory = get_session_factory()
            async with session_factory() as session:
                async with session.begin():
                    # 1. Ensure Guild exists
                    guild, _ = await get_or_create_guild(
                        session=session,
                        discord_guild_id=member.guild.id,
                        name=member.guild.name,
                    )
                    # 2. Ensure User exists or is created/updated
                    user, _ = await get_or_create_user(
                        session=session,
                        discord_user_id=member.id,
                        username=member.name,
                        global_name=member.global_name or member.display_name,
                    )
                    # 3. Ensure GuildMember relationship exists
                    db_member, _ = await get_or_create_guild_member(
                        session=session,
                        guild_id=guild.id,
                        user_id=user.id,
                        joined_at=member.joined_at,
                    )
                    # 4. Assign non-default roles
                    for role in member.roles:
                        if role.is_default() or role.name == "@everyone":
                            continue
                        db_role, _ = await get_or_create_role(
                            session=session,
                            guild_id=guild.id,
                            discord_role_id=role.id,
                            name=role.name,
                            position=role.position,
                        )
                        await assign_guild_member_role(
                            session=session,
                            guild_member_id=db_member.id,
                            role_id=db_role.id,
                        )
        except Exception as exc:
            logger.error(
                f"Error persisting guild member join for user {member.id} in guild {member.guild.id}: {exc}"
            )

    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        """Event fired when a member's properties (such as roles) are updated in a Discord guild."""
        before_role_ids = {r.id for r in before.roles if not (r.is_default() or r.name == "@everyone")}
        after_role_ids = {r.id for r in after.roles if not (r.is_default() or r.name == "@everyone")}

        if before_role_ids == after_role_ids:
            return

        logger.info(
            f"Member roles updated for {after} (ID: {after.id}) in guild {after.guild.name} (ID: {after.guild.id})"
        )

        added_role_ids = after_role_ids - before_role_ids
        removed_role_ids = before_role_ids - after_role_ids

        try:
            session_factory = get_session_factory()
            async with session_factory() as session:
                async with session.begin():
                    # 1. Ensure Guild exists
                    db_guild, _ = await get_or_create_guild(
                        session=session,
                        discord_guild_id=after.guild.id,
                        name=after.guild.name,
                    )
                    # 2. Ensure User exists
                    db_user, _ = await get_or_create_user(
                        session=session,
                        discord_user_id=after.id,
                        username=after.name,
                        global_name=after.global_name or after.display_name,
                    )
                    # 3. Ensure GuildMember exists
                    db_member, _ = await get_or_create_guild_member(
                        session=session,
                        guild_id=db_guild.id,
                        user_id=db_user.id,
                        joined_at=after.joined_at,
                    )

                    # Process added roles
                    if added_role_ids:
                        roles_by_id = {r.id: r for r in after.roles}
                        for role_id in added_role_ids:
                            discord_role = roles_by_id.get(role_id)
                            if discord_role is not None:
                                db_role, _ = await get_or_create_role(
                                    session=session,
                                    guild_id=db_guild.id,
                                    discord_role_id=discord_role.id,
                                    name=discord_role.name,
                                    position=discord_role.position,
                                )
                                await assign_guild_member_role(
                                    session=session,
                                    guild_member_id=db_member.id,
                                    role_id=db_role.id,
                                )

                    # Process removed roles
                    if removed_role_ids:
                        for role_id in removed_role_ids:
                            db_role = await get_role(session, db_guild.id, role_id)
                            if db_role is not None:
                                await remove_guild_member_role(
                                    session=session,
                                    guild_member_id=db_member.id,
                                    role_id=db_role.id,
                                )
        except Exception as exc:
            logger.error(
                f"Error processing member role update for user {after.id} in guild {after.guild.id}: {exc}"
            )

    async def on_guild_role_create(self, role: discord.Role) -> None:
        """Event fired when a new role is created in a Discord guild."""
        if role.is_default() or role.name == "@everyone":
            return
        logger.info(f"Role created in guild {role.guild.name}: {role.name} (ID: {role.id})")
        try:
            session_factory = get_session_factory()
            async with session_factory() as session:
                async with session.begin():
                    db_guild, _ = await get_or_create_guild(
                        session=session,
                        discord_guild_id=role.guild.id,
                        name=role.guild.name,
                    )
                    await get_or_create_role(
                        session=session,
                        guild_id=db_guild.id,
                        discord_role_id=role.id,
                        name=role.name,
                        position=role.position,
                    )
        except Exception as exc:
            logger.error(f"Error persisting role creation for role {role.id}: {exc}")

    async def on_guild_role_update(self, before: discord.Role, after: discord.Role) -> None:
        """Event fired when a role is updated in a Discord guild."""
        if after.is_default() or after.name == "@everyone":
            return
        logger.info(f"Role updated in guild {after.guild.name}: {after.name} (ID: {after.id})")
        try:
            session_factory = get_session_factory()
            async with session_factory() as session:
                async with session.begin():
                    db_guild, _ = await get_or_create_guild(
                        session=session,
                        discord_guild_id=after.guild.id,
                        name=after.guild.name,
                    )
                    await get_or_create_role(
                        session=session,
                        guild_id=db_guild.id,
                        discord_role_id=after.id,
                        name=after.name,
                        position=after.position,
                    )
        except Exception as exc:
            logger.error(f"Error persisting role update for role {after.id}: {exc}")

    async def on_guild_role_delete(self, role: discord.Role) -> None:
        """Event fired when a role is deleted from a Discord guild."""
        if role.is_default() or role.name == "@everyone":
            return
        logger.info(f"Role deleted in guild {role.guild.name}: {role.name} (ID: {role.id})")
        try:
            session_factory = get_session_factory()
            async with session_factory() as session:
                async with session.begin():
                    db_guild = await get_guild_by_discord_id(session, role.guild.id)
                    if db_guild is not None:
                        await delete_role(
                            session=session,
                            guild_id=db_guild.id,
                            discord_role_id=role.id,
                        )
        except Exception as exc:
            logger.error(f"Error persisting role deletion for role {role.id}: {exc}")

    async def close(self) -> None:
        """Gracefully disposes database resources and closes Discord websocket connections."""
        logger.info("Initiating graceful application shutdown...")
        try:
            await close_db_engine()
        except Exception as exc:
            logger.error(f"Error during database engine shutdown: {exc}")

        await super().close()
        logger.info("Discord gateway connection closed cleanly.")
