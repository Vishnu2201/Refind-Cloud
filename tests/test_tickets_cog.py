"""Unit tests for TicketsCog Discord slash command and button interactions."""

from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import discord
import pytest

from app.bot.cogs.tickets import TicketsCog, handle_close_ticket_interaction
from app.modules.guilds.models import Guild
from app.modules.tickets.models import Ticket, TicketStatus
from app.modules.users.models import User


def create_mock_interaction(
    guild_id: int | None = 123456789,
    user_id: int = 987654321,
    channel_id: int = 555666777,
    is_done: bool = False,
) -> MagicMock:
    """Helper creating a mock discord.Interaction for unit testing."""
    interaction = MagicMock(spec=discord.Interaction)
    interaction.guild_id = guild_id

    if guild_id is not None:
        guild = MagicMock(spec=discord.Guild)
        guild.id = guild_id
        guild.name = "Test Guild"
        guild.default_role = MagicMock(spec=discord.Role)
        guild.me = MagicMock(spec=discord.Member)
        interaction.guild = guild
    else:
        interaction.guild = None

    user = MagicMock(spec=discord.Member)
    user.id = user_id
    user.name = "testuser"
    user.global_name = "Test User"
    user.mention = f"<@{user_id}>"
    user.joined_at = None
    interaction.user = user

    if channel_id is not None:
        channel = MagicMock(spec=discord.TextChannel)
        channel.id = channel_id
        interaction.channel = channel
    else:
        interaction.channel = None

    interaction.response = AsyncMock()
    interaction.response.is_done.return_value = is_done
    interaction.followup = AsyncMock()
    return interaction


@pytest.mark.asyncio
async def test_ticket_command_rejects_dms() -> None:
    """Verifies that the /ticket command rejects interactions outside a guild."""
    bot = MagicMock()
    cog = TicketsCog(bot)
    interaction = create_mock_interaction(guild_id=None)

    await cog.ticket.callback(cog, interaction, subject="Help request")

    interaction.response.send_message.assert_awaited_once_with(
        content="Support tickets can only be opened inside a server.",
        embed=None,
        view=None,
        ephemeral=True,
    )


@pytest.mark.asyncio
@patch("app.bot.cogs.tickets.get_session_factory")
@patch("app.bot.cogs.tickets.get_or_create_guild")
@patch("app.bot.cogs.tickets.get_or_create_user")
@patch("app.bot.cogs.tickets.get_or_create_guild_member")
@patch("app.bot.cogs.tickets.get_open_ticket_for_user")
async def test_ticket_command_existing_open_ticket(
    mock_get_open_ticket: AsyncMock,
    mock_get_member: AsyncMock,
    mock_get_user: AsyncMock,
    mock_get_guild: AsyncMock,
    mock_session_factory: MagicMock,
) -> None:
    """Verifies user with an existing open ticket cannot open a second one."""
    bot = MagicMock()
    cog = TicketsCog(bot)
    interaction = create_mock_interaction()

    mock_db_guild = Guild(id=uuid.uuid4(), discord_guild_id=123456789, name="Test Guild")
    mock_db_user = User(id=uuid.uuid4(), discord_user_id=987654321, username="testuser")
    mock_existing_ticket = Ticket(
        id=uuid.uuid4(),
        guild_id=mock_db_guild.id,
        user_id=mock_db_user.id,
        status=TicketStatus.OPEN,
        discord_channel_id=555666777,
    )

    mock_get_guild.return_value = (mock_db_guild, False)
    mock_get_user.return_value = (mock_db_user, False)
    mock_get_open_ticket.return_value = mock_existing_ticket

    mock_session = AsyncMock()
    mock_session_factory.return_value.return_value.__aenter__.return_value = mock_session
    mock_session.begin.return_value.__aenter__.return_value = None

    await cog.ticket.callback(cog, interaction, subject="Duplicate test")

    interaction.response.send_message.assert_awaited_once()
    call_args = interaction.response.send_message.call_args[1]["content"]
    assert "already have an open support ticket" in call_args
    assert "<#555666777>" in call_args


@pytest.mark.asyncio
@patch("app.bot.cogs.tickets.get_session_factory")
@patch("app.bot.cogs.tickets.get_or_create_guild")
@patch("app.bot.cogs.tickets.get_or_create_user")
@patch("app.bot.cogs.tickets.get_or_create_guild_member")
@patch("app.bot.cogs.tickets.get_open_ticket_for_user")
@patch("app.bot.cogs.tickets.create_ticket")
@patch("app.bot.cogs.tickets.set_ticket_discord_channel")
async def test_ticket_command_successful_creation(
    mock_set_channel: AsyncMock,
    mock_create_ticket: AsyncMock,
    mock_get_open_ticket: AsyncMock,
    mock_get_member: AsyncMock,
    mock_get_user: AsyncMock,
    mock_get_guild: AsyncMock,
    mock_session_factory: MagicMock,
) -> None:
    """Verifies successful ticket creation creates DB ticket, text channel, links ID, and sends message."""
    bot = MagicMock()
    cog = TicketsCog(bot)
    interaction = create_mock_interaction()

    mock_db_guild = Guild(id=uuid.uuid4(), discord_guild_id=123456789, name="Test Guild")
    mock_db_user = User(id=uuid.uuid4(), discord_user_id=987654321, username="testuser")
    mock_ticket_id = uuid.uuid4()
    mock_new_ticket = Ticket(
        id=mock_ticket_id,
        guild_id=mock_db_guild.id,
        user_id=mock_db_user.id,
        subject="Billing issue",
        status=TicketStatus.OPEN,
    )

    mock_get_guild.return_value = (mock_db_guild, False)
    mock_get_user.return_value = (mock_db_user, False)
    mock_get_open_ticket.return_value = None
    mock_create_ticket.return_value = mock_new_ticket

    mock_channel = AsyncMock(spec=discord.TextChannel)
    mock_channel.id = 888999000
    mock_channel.mention = "<#888999000>"
    interaction.guild.create_text_channel.return_value = mock_channel

    mock_session = AsyncMock()
    mock_session_factory.return_value.return_value.__aenter__.return_value = mock_session
    mock_session.begin.return_value.__aenter__.return_value = None

    await cog.ticket.callback(cog, interaction, subject="Billing issue")

    mock_create_ticket.assert_awaited_once_with(
        session=mock_session,
        guild_id=mock_db_guild.id,
        user_id=mock_db_user.id,
        subject="Billing issue",
    )

    short_uuid = str(mock_ticket_id)[:8]
    interaction.guild.create_text_channel.assert_awaited_once()
    channel_kwargs = interaction.guild.create_text_channel.call_args[1]
    assert channel_kwargs["name"] == f"ticket-{short_uuid}"

    mock_set_channel.assert_awaited_once_with(
        session=mock_session,
        ticket_id=mock_ticket_id,
        discord_channel_id=888999000,
    )

    mock_channel.send.assert_awaited_once()
    interaction.response.send_message.assert_awaited_once()


@pytest.mark.asyncio
@patch("app.bot.cogs.tickets.get_session_factory")
@patch("app.bot.cogs.tickets.get_or_create_guild")
@patch("app.bot.cogs.tickets.get_or_create_user")
@patch("app.bot.cogs.tickets.get_or_create_guild_member")
@patch("app.bot.cogs.tickets.get_open_ticket_for_user")
@patch("app.bot.cogs.tickets.create_ticket")
@patch("app.bot.cogs.tickets.close_ticket")
async def test_ticket_command_channel_creation_failure_rollback(
    mock_close_ticket: AsyncMock,
    mock_create_ticket: AsyncMock,
    mock_get_open_ticket: AsyncMock,
    mock_get_member: AsyncMock,
    mock_get_user: AsyncMock,
    mock_get_guild: AsyncMock,
    mock_session_factory: MagicMock,
) -> None:
    """Verifies that channel creation failure marks DB ticket closed to prevent orphaned open ticket."""
    bot = MagicMock()
    cog = TicketsCog(bot)
    interaction = create_mock_interaction()

    mock_db_guild = Guild(id=uuid.uuid4(), discord_guild_id=123456789, name="Test Guild")
    mock_db_user = User(id=uuid.uuid4(), discord_user_id=987654321, username="testuser")
    mock_ticket_id = uuid.uuid4()
    mock_new_ticket = Ticket(
        id=mock_ticket_id,
        guild_id=mock_db_guild.id,
        user_id=mock_db_user.id,
        subject="Failed channel",
    )

    mock_get_guild.return_value = (mock_db_guild, False)
    mock_get_user.return_value = (mock_db_user, False)
    mock_get_open_ticket.return_value = None
    mock_create_ticket.return_value = mock_new_ticket

    interaction.guild.create_text_channel.side_effect = discord.Forbidden(
        response=MagicMock(), message="Missing Permissions"
    )

    mock_session = AsyncMock()
    mock_session_factory.return_value.return_value.__aenter__.return_value = mock_session
    mock_session.begin.return_value.__aenter__.return_value = None

    await cog.ticket.callback(cog, interaction, subject="Failed channel")

    mock_close_ticket.assert_awaited_once_with(mock_session, mock_ticket_id)
    interaction.response.send_message.assert_awaited_once()
    call_args = interaction.response.send_message.call_args[1]["content"]
    assert "Failed to create a support ticket channel" in call_args


@pytest.mark.asyncio
@patch("app.bot.cogs.tickets.get_session_factory")
@patch("app.bot.cogs.tickets.get_or_create_guild")
@patch("app.bot.cogs.tickets.get_or_create_user")
@patch("app.bot.cogs.tickets.get_or_create_guild_member")
@patch("app.bot.cogs.tickets.get_open_ticket_for_user")
@patch("app.bot.cogs.tickets.create_ticket")
@patch("app.bot.cogs.tickets.set_ticket_discord_channel")
@patch("app.bot.cogs.tickets.close_ticket")
async def test_ticket_command_channel_link_failure_cleanup(
    mock_close_ticket: AsyncMock,
    mock_set_channel: AsyncMock,
    mock_create_ticket: AsyncMock,
    mock_get_open_ticket: AsyncMock,
    mock_get_member: AsyncMock,
    mock_get_user: AsyncMock,
    mock_get_guild: AsyncMock,
    mock_session_factory: MagicMock,
) -> None:
    """Verifies that DB channel link failure deletes Discord channel and closes DB ticket."""
    bot = MagicMock()
    cog = TicketsCog(bot)
    interaction = create_mock_interaction()

    mock_db_guild = Guild(id=uuid.uuid4(), discord_guild_id=123456789, name="Test Guild")
    mock_db_user = User(id=uuid.uuid4(), discord_user_id=987654321, username="testuser")
    mock_ticket_id = uuid.uuid4()
    mock_new_ticket = Ticket(id=mock_ticket_id, guild_id=mock_db_guild.id, user_id=mock_db_user.id, subject="Link Fail")

    mock_get_guild.return_value = (mock_db_guild, False)
    mock_get_user.return_value = (mock_db_user, False)
    mock_get_open_ticket.return_value = None
    mock_create_ticket.return_value = mock_new_ticket

    mock_channel = AsyncMock(spec=discord.TextChannel)
    mock_channel.id = 888999000
    interaction.guild.create_text_channel.return_value = mock_channel

    mock_set_channel.side_effect = RuntimeError("DB Connection Loss")

    mock_session = AsyncMock()
    mock_session_factory.return_value.return_value.__aenter__.return_value = mock_session
    mock_session.begin.return_value.__aenter__.return_value = None

    await cog.ticket.callback(cog, interaction, subject="Link Fail")

    # Channel should be deleted
    mock_channel.delete.assert_awaited_once()
    # Ticket should be closed in DB
    mock_close_ticket.assert_awaited_once_with(mock_session, mock_ticket_id)
    # User receives error response
    interaction.response.send_message.assert_awaited_once()


@pytest.mark.asyncio
@patch("app.bot.cogs.tickets.get_session_factory")
@patch("app.bot.cogs.tickets.get_or_create_guild")
@patch("app.bot.cogs.tickets.get_or_create_user")
@patch("app.bot.cogs.tickets.get_or_create_guild_member")
@patch("app.bot.cogs.tickets.get_open_ticket_for_user")
@patch("app.bot.cogs.tickets.create_ticket")
@patch("app.bot.cogs.tickets.set_ticket_discord_channel")
async def test_ticket_command_welcome_message_failure(
    mock_set_channel: AsyncMock,
    mock_create_ticket: AsyncMock,
    mock_get_open_ticket: AsyncMock,
    mock_get_member: AsyncMock,
    mock_get_user: AsyncMock,
    mock_get_guild: AsyncMock,
    mock_session_factory: MagicMock,
) -> None:
    """Verifies that if sending welcome message fails, user still receives interaction response."""
    bot = MagicMock()
    cog = TicketsCog(bot)
    interaction = create_mock_interaction()

    mock_db_guild = Guild(id=uuid.uuid4(), discord_guild_id=123456789, name="Test Guild")
    mock_db_user = User(id=uuid.uuid4(), discord_user_id=987654321, username="testuser")
    mock_ticket_id = uuid.uuid4()
    mock_new_ticket = Ticket(id=mock_ticket_id, guild_id=mock_db_guild.id, user_id=mock_db_user.id, subject="Welcome Fail")

    mock_get_guild.return_value = (mock_db_guild, False)
    mock_get_user.return_value = (mock_db_user, False)
    mock_get_open_ticket.return_value = None
    mock_create_ticket.return_value = mock_new_ticket

    mock_channel = AsyncMock(spec=discord.TextChannel)
    mock_channel.id = 888999000
    mock_channel.mention = "<#888999000>"
    mock_channel.send.side_effect = discord.HTTPException(response=MagicMock(), message="Cannot Send Embed")
    interaction.guild.create_text_channel.return_value = mock_channel

    mock_session = AsyncMock()
    mock_session_factory.return_value.return_value.__aenter__.return_value = mock_session
    mock_session.begin.return_value.__aenter__.return_value = None

    await cog.ticket.callback(cog, interaction, subject="Welcome Fail")

    # Interaction response should still be sent to user
    interaction.response.send_message.assert_awaited_once()


@pytest.mark.asyncio
@patch("app.bot.cogs.tickets.get_session_factory")
@patch("app.bot.cogs.tickets.get_ticket_by_discord_channel_id")
@patch("app.bot.cogs.tickets.close_ticket")
async def test_close_ticket_button_success(
    mock_close_ticket: AsyncMock,
    mock_get_ticket_by_channel: AsyncMock,
    mock_session_factory: MagicMock,
) -> None:
    """Verifies Close Ticket button finds ticket by channel ID and updates status to CLOSED."""
    interaction = create_mock_interaction(channel_id=555666777)
    mock_ticket_id = uuid.uuid4()
    mock_ticket = Ticket(
        id=mock_ticket_id,
        guild_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        discord_channel_id=555666777,
        status=TicketStatus.OPEN,
    )

    mock_get_ticket_by_channel.return_value = mock_ticket

    mock_session = AsyncMock()
    mock_session_factory.return_value.return_value.__aenter__.return_value = mock_session
    mock_session.begin.return_value.__aenter__.return_value = None

    await handle_close_ticket_interaction(interaction)

    mock_get_ticket_by_channel.assert_awaited_once_with(mock_session, 555666777)
    mock_close_ticket.assert_awaited_once_with(mock_session, mock_ticket_id)
    interaction.response.send_message.assert_awaited_once()


@pytest.mark.asyncio
@patch("app.bot.cogs.tickets.get_session_factory")
@patch("app.bot.cogs.tickets.get_ticket_by_discord_channel_id")
async def test_close_ticket_button_already_closed(
    mock_get_ticket_by_channel: AsyncMock,
    mock_session_factory: MagicMock,
) -> None:
    """Verifies pressing Close Ticket on an already closed ticket is handled safely."""
    interaction = create_mock_interaction(channel_id=555666777)
    mock_ticket = Ticket(
        id=uuid.uuid4(),
        guild_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        discord_channel_id=555666777,
        status=TicketStatus.CLOSED,
    )

    mock_get_ticket_by_channel.return_value = mock_ticket

    mock_session = AsyncMock()
    mock_session_factory.return_value.return_value.__aenter__.return_value = mock_session
    mock_session.begin.return_value.__aenter__.return_value = None

    await handle_close_ticket_interaction(interaction)

    interaction.response.send_message.assert_awaited_once_with(
        content="This support ticket is already closed.",
        embed=None,
        view=None,
        ephemeral=True,
    )


@pytest.mark.asyncio
@patch("app.bot.cogs.tickets.get_session_factory")
@patch("app.bot.cogs.tickets.get_ticket_by_discord_channel_id")
async def test_close_ticket_button_non_ticket_channel(
    mock_get_ticket_by_channel: AsyncMock,
    mock_session_factory: MagicMock,
) -> None:
    """Verifies pressing Close Ticket in a non-ticket channel is handled safely."""
    interaction = create_mock_interaction(channel_id=999999999)
    mock_get_ticket_by_channel.return_value = None

    mock_session = AsyncMock()
    mock_session_factory.return_value.return_value.__aenter__.return_value = mock_session
    mock_session.begin.return_value.__aenter__.return_value = None

    await handle_close_ticket_interaction(interaction)

    interaction.response.send_message.assert_awaited_once_with(
        content="This channel is not associated with an active support ticket.",
        embed=None,
        view=None,
        ephemeral=True,
    )
