"""SQLAlchemy ORM model for Discord Role identity and tracking."""

import datetime
import uuid

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Role(Base):
    """Represents a persisted Discord role associated with a guild in Refind Cloud."""

    __tablename__ = "roles"
    __table_args__ = (
        UniqueConstraint("guild_id", "discord_role_id", name="uq_roles_guild_discord_role"),
    )

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
    discord_role_id: Mapped[int] = mapped_column(
        BigInteger,
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(
        Integer,
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

    def __repr__(self) -> str:
        return f"<Role id={self.id} guild_id={self.guild_id} discord_role_id={self.discord_role_id} name='{self.name}'>"
