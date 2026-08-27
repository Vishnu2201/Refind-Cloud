"""Discord bot cog managing support ticket creation, channel management, and closure."""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from app.database.session import get_session_factory
from app.modules.guild_members.service import get_or_create_guild_member
from app.modules.guilds.service import get_or_create_guild
from app.modules.tickets.models import TicketStatus
from app.modules.tickets.service import (
    close_ticket,
    create_ticket,
    get_open_ticket_for_user,
    get_ticket_by_discord_channel_id,
    set_ticket_discord_channel,
)
from app.modules.users.service import get_or_create_user

logger = logging.getLogger(__name__)


async def send_interaction_response(
    interaction: discord.Interaction,
    content: str | None = None,
    *,
    embed: discord.Embed | None = None,
    view: discord.ui.View | None = None,
    ephemeral: bool = True,
) -> None:
    """Helper safely delivering interaction responses, using followup if already responded."""
    if interaction.response.is_done():
        await interaction.followup.send(
            content=content,
            embed=embed,
            view=view,
            ephemeral=ephemeral,
        )
    else:
        await interaction.response.send_message(
            content=content,
            embed=embed,
            view=view,
            ephemeral=ephemeral,
        )


class CloseTicketButton(discord.ui.Button):
    """Interactive button allowing users or staff to close an active support ticket."""

    def __init__(self) -> None:
        super().__init__(
            label="Close Ticket",
            style=discord.ButtonStyle.danger,
            custom_id="ticket_close_button",
            emoji="🔒",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        """Callback executed when the Close Ticket button is pressed."""
        await handle_close_ticket_interaction(interaction)


class TicketView(discord.ui.View):
    """Persistent Discord UI View attached to ticket welcome messages."""

    def __init__(self) -> None:
        super().__init__(timeout=None)
        self.add_item(CloseTicketButton())


async def handle_close_ticket_interaction(interaction: discord.Interaction) -> None:
    """Processes ticket closure when the Close Ticket button is clicked."""
    if interaction.channel is None or not hasattr(interaction.channel, "id"):
        await send_interaction_response(
            interaction,
            "This interaction must be executed inside a ticket channel.",
            ephemeral=True,
        )
        return

    discord_channel_id = interaction.channel.id
    session_factory = get_session_factory()

    async with session_factory() as session:
        async with session.begin():
            ticket = await get_ticket_by_discord_channel_id(session, discord_channel_id)
            if ticket is None:
                await send_interaction_response(
                    interaction,
                    "This channel is not associated with an active support ticket.",
                    ephemeral=True,
                )
                return

            if ticket.status == TicketStatus.CLOSED:
                await send_interaction_response(
                    interaction,
                    "This support ticket is already closed.",
                    ephemeral=True,
                )
                return

            await close_ticket(session, ticket.id)

    closed_embed = discord.Embed(
        title="🔒 Support Ticket Closed",
        description=(
            f"This ticket has been marked as **CLOSED** by {interaction.user.mention}.\n"
            f"The conversation history remains visible in this channel for record keeping."
        ),
        color=discord.Color.red(),
    )

    await send_interaction_response(
        interaction,
        embed=closed_embed,
        ephemeral=False,
    )

    logger.info(
        f"Ticket {ticket.id} closed via button in channel {discord_channel_id} by user {interaction.user.id}"
    )


class TicketsCog(commands.Cog):
    """Cog handling Discord support ticket creation and channel lifecycle management."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # Register persistent view for button callback support across bot restarts
        self.bot.add_view(TicketView())

    @app_commands.command(
        name="ticket",
        description="Open a new support ticket.",
    )
    @app_commands.describe(subject="Brief description of your support request")
    async def ticket(self, interaction: discord.Interaction, subject: str) -> None:
        """Slash command creating a new support ticket and private Discord channel."""
        if interaction.guild is None or interaction.guild_id is None:
            await send_interaction_response(
                interaction,
                "Support tickets can only be opened inside a server.",
                ephemeral=True,
            )
            return

        discord_user = interaction.user
        discord_user_id = discord_user.id
        username = discord_user.name
        global_name = discord_user.global_name or discord_user.display_name

        session_factory = get_session_factory()

        # Step 1: Resolve DB User, Guild, GuildMember & Check for Existing Open Ticket
        async with session_factory() as session:
            async with session.begin():
                db_guild, _ = await get_or_create_guild(
                    session=session,
                    discord_guild_id=interaction.guild.id,
                    name=interaction.guild.name,
                )
                db_user, _ = await get_or_create_user(
                    session=session,
                    discord_user_id=discord_user_id,
                    username=username,
                    global_name=global_name,
                )
                await get_or_create_guild_member(
                    session=session,
                    guild_id=db_guild.id,
                    user_id=db_user.id,
                    joined_at=getattr(discord_user, "joined_at", None),
                )
                existing_open_ticket = await get_open_ticket_for_user(
                    session=session,
                    guild_id=db_guild.id,
                    user_id=db_user.id,
                )

        # Step 2: Handle Existing Open Ticket
        if existing_open_ticket is not None:
            channel_ref = (
                f" in <#{existing_open_ticket.discord_channel_id}>"
                if existing_open_ticket.discord_channel_id
                else ""
            )
            await send_interaction_response(
                interaction,
                f"You already have an open support ticket{channel_ref}. Please resolve your existing ticket before opening a new one.",
                ephemeral=True,
            )
            return

        # Step 3: Phase A - Create Database Ticket Record
        async with session_factory() as session:
            async with session.begin():
                db_ticket = await create_ticket(
                    session=session,
                    guild_id=db_guild.id,
                    user_id=db_user.id,
                    subject=subject,
                )
                ticket_id = db_ticket.id

        # Step 4: Phase B - Create Private Discord Channel
        short_id = str(ticket_id)[:8]
        channel_name = f"ticket-{short_id}"

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(
                read_messages=False,
                view_channel=False,
            ),
            discord_user: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                view_channel=True,
                attach_files=True,
                embed_links=True,
            ),
        }

        # Grant bot permission to manage channel
        bot_member = interaction.guild.me
        if bot_member is not None:
            overwrites[bot_member] = discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                view_channel=True,
                manage_channels=True,
                manage_messages=True,
            )

        try:
            ticket_channel = await interaction.guild.create_text_channel(
                name=channel_name,
                overwrites=overwrites,
                reason=f"Support ticket opened by {discord_user} (Subject: {subject})",
            )
        except Exception as channel_exc:
            logger.error(
                f"Failed to create Discord text channel for ticket {ticket_id}: {channel_exc}"
            )
            # Rollback DB ticket state by closing ticket so no orphaned open ticket remains
            try:
                async with session_factory() as session:
                    async with session.begin():
                        await close_ticket(session, ticket_id)
            except Exception as rollback_exc:
                logger.critical(
                    f"CRITICAL: Failed to close ticket {ticket_id} during channel creation rollback: {rollback_exc}"
                )

            await send_interaction_response(
                interaction,
                "Failed to create a support ticket channel. Please contact a server administrator.",
                ephemeral=True,
            )
            return

        # Step 5: Phase C - Link Channel ID to Ticket Record
        try:
            async with session_factory() as session:
                async with session.begin():
                    await set_ticket_discord_channel(
                        session=session,
                        ticket_id=ticket_id,
                        discord_channel_id=ticket_channel.id,
                    )
        except Exception as link_exc:
            logger.error(
                f"Failed to link discord_channel_id {ticket_channel.id} to ticket {ticket_id}: {link_exc}"
            )
            # Delete created channel to keep Discord and DB consistent, and mark ticket closed
            try:
                await ticket_channel.delete(
                    reason="Database linking failed during ticket creation"
                )
            except Exception as delete_exc:
                logger.error(f"Failed to delete channel after DB link failure: {delete_exc}")

            try:
                async with session_factory() as session:
                    async with session.begin():
                        await close_ticket(session, ticket_id)
            except Exception as rollback_exc:
                logger.critical(
                    f"CRITICAL: Failed to close ticket {ticket_id} during link failure rollback: {rollback_exc}"
                )

            await send_interaction_response(
                interaction,
                "An error occurred while linking your ticket. Please try again.",
                ephemeral=True,
            )
            return

        # Step 6: Phase D - Send Welcome Message in Ticket Channel & Respond to Interaction
        try:
            welcome_embed = discord.Embed(
                title=f"Support Ticket: {subject}",
                description=(
                    f"Hello {discord_user.mention}! Thank you for reaching out.\n"
                    f"Our support team has been notified and will assist you shortly.\n\n"
                    f"**Subject**: {subject}\n"
                    f"**Ticket ID**: `{ticket_id}`"
                ),
                color=discord.Color.blue(),
            )

            await ticket_channel.send(
                content=discord_user.mention,
                embed=welcome_embed,
                view=TicketView(),
            )
        except Exception as welcome_exc:
            logger.warning(
                f"Failed to send welcome embed in ticket channel {ticket_channel.id}: {welcome_exc}"
            )

        await send_interaction_response(
            interaction,
            f"Your support ticket has been created in {ticket_channel.mention}.",
            ephemeral=True,
        )

        logger.info(
            f"Successfully created ticket {ticket_id} and channel {ticket_channel.id} for user {discord_user_id}"
        )


async def setup(bot: commands.Bot) -> None:
    """Extension setup entry point for TicketsCog registration."""
    await bot.add_cog(TicketsCog(bot))
