"""Custom Discord bot client managing async lifecycle hooks and command synchronization."""

import logging

import discord
from discord.ext import commands

from app.core.context import get_app_context
from app.database.session import check_database_health, close_db_engine, get_session_factory, init_db_resources
from app.modules.guild_members.service import get_or_create_guild_member
from app.modules.guilds.service import get_or_create_guild
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
        """Persists all connected Discord guilds into PostgreSQL on startup."""
        if not self.guilds:
            return

        session_factory = get_session_factory()
        async with session_factory() as session:
            async with session.begin():
                for guild in self.guilds:
                    await get_or_create_guild(
                        session=session,
                        discord_guild_id=guild.id,
                        name=guild.name,
                    )
        logger.info(f"Registered {len(self.guilds)} connected Discord guild(s) in database.")

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

        # Persist connected guilds into database
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
                    await get_or_create_guild(
                        session=session,
                        discord_guild_id=guild.id,
                        name=guild.name,
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
                    await get_or_create_guild_member(
                        session=session,
                        guild_id=guild.id,
                        user_id=user.id,
                        joined_at=member.joined_at,
                    )
        except Exception as exc:
            logger.error(
                f"Error persisting guild member join for user {member.id} in guild {member.guild.id}: {exc}"
            )

    async def close(self) -> None:
        """Gracefully disposes database resources and closes Discord websocket connections."""
        logger.info("Initiating graceful application shutdown...")
        try:
            await close_db_engine()
        except Exception as exc:
            logger.error(f"Error during database engine shutdown: {exc}")

        await super().close()
        logger.info("Discord gateway connection closed cleanly.")
