"""Support Tickets domain module."""

from app.modules.tickets.models import Ticket, TicketStatus
from app.modules.tickets.service import (
    close_ticket,
    create_ticket,
    get_open_ticket_for_user,
    get_ticket,
    get_ticket_by_discord_channel_id,
    set_ticket_discord_channel,
)

__all__ = [
    "Ticket",
    "TicketStatus",
    "create_ticket",
    "get_ticket",
    "get_ticket_by_discord_channel_id",
    "set_ticket_discord_channel",
    "close_ticket",
    "get_open_ticket_for_user",
]
