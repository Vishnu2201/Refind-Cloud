"""SQLAlchemy ORM model and enum for Support Tickets."""

import datetime
import enum
import uuid

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class TicketStatus(str, enum.Enum):
    """Lifecycle status for support tickets."""

    OPEN = "open"
    CLOSED = "closed"


class Ticket(Base):
    """Represents a support ticket in Refind Cloud."""

    __tablename__ = "tickets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    guild_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("guilds.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    discord_channel_id: Mapped[int | None] = mapped_column(
        BigInteger,
        unique=True,
        index=True,
        nullable=True,
    )
    status: Mapped[TicketStatus] = mapped_column(
        Enum(
            TicketStatus,
            native_enum=False,
            length=50,
            values_callable=lambda x: [e.value for e in x],
        ),
        default=TicketStatus.OPEN,
        server_default=TicketStatus.OPEN.value,
        nullable=False,
    )
    subject: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    closed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<Ticket id={self.id} guild_id={self.guild_id} user_id={self.user_id} status='{self.status}'>"
