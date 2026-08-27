"""create_tickets_table

Revision ID: 20260827_0002
Revises: 20260827_0001
Create Date: 2026-08-27 21:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260827_0002"
down_revision: Union[str, None] = "20260827_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create tickets table with foreign keys, indexes, and unique constraints."""
    op.create_table(
        "tickets",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("guild_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("discord_channel_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "open",
                "closed",
                name="ticketstatus",
                native_enum=False,
                length=50,
            ),
            server_default="open",
            nullable=False,
        ),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["guild_id"], ["guilds.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_tickets_discord_channel_id"),
        "tickets",
        ["discord_channel_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_tickets_guild_id"),
        "tickets",
        ["guild_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tickets_user_id"),
        "tickets",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop tickets table and associated indexes."""
    op.drop_index(op.f("ix_tickets_user_id"), table_name="tickets")
    op.drop_index(op.f("ix_tickets_guild_id"), table_name="tickets")
    op.drop_index(op.f("ix_tickets_discord_channel_id"), table_name="tickets")
    op.drop_table("tickets")
