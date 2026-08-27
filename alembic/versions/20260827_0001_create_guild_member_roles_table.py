"""create_initial_foundation_schema

Revision ID: 20260827_0001
Revises: 
Create Date: 2026-08-27 18:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260827_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial foundation tables in dependency order."""
    # Ensure pgcrypto extension is available for gen_random_uuid() on older PostgreSQL instances
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    # 1. users table
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("discord_user_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("global_name", sa.String(length=255), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_users_discord_user_id"),
        "users",
        ["discord_user_id"],
        unique=True,
    )

    # 2. guilds table
    op.create_table(
        "guilds",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("discord_guild_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_guilds_discord_guild_id"),
        "guilds",
        ["discord_guild_id"],
        unique=True,
    )

    # 3. guild_members table
    op.create_table(
        "guild_members",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("guild_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["guild_id"], ["guilds.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "guild_id", "user_id", name="uq_guild_members_guild_user"
        ),
    )
    op.create_index(
        op.f("ix_guild_members_guild_id"),
        "guild_members",
        ["guild_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_guild_members_user_id"),
        "guild_members",
        ["user_id"],
        unique=False,
    )

    # 4. guild_settings table
    op.create_table(
        "guild_settings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("guild_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "feature_enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
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
        sa.ForeignKeyConstraint(
            ["guild_id"], ["guilds.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_guild_settings_guild_id"),
        "guild_settings",
        ["guild_id"],
        unique=True,
    )

    # 5. roles table
    op.create_table(
        "roles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("guild_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("discord_role_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["guild_id"], ["guilds.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "guild_id", "discord_role_id", name="uq_roles_guild_discord_role"
        ),
    )
    op.create_index(
        op.f("ix_roles_discord_role_id"),
        "roles",
        ["discord_role_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_roles_guild_id"),
        "roles",
        ["guild_id"],
        unique=False,
    )

    # 6. guild_member_roles table
    op.create_table(
        "guild_member_roles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("guild_member_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["guild_member_id"], ["guild_members.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["role_id"], ["roles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "guild_member_id",
            "role_id",
            name="uq_guild_member_roles_member_role",
        ),
    )
    op.create_index(
        op.f("ix_guild_member_roles_guild_member_id"),
        "guild_member_roles",
        ["guild_member_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_guild_member_roles_role_id"),
        "guild_member_roles",
        ["role_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop tables in reverse dependency order."""
    op.drop_index(
        op.f("ix_guild_member_roles_role_id"), table_name="guild_member_roles"
    )
    op.drop_index(
        op.f("ix_guild_member_roles_guild_member_id"),
        table_name="guild_member_roles",
    )
    op.drop_table("guild_member_roles")

    op.drop_index(op.f("ix_roles_guild_id"), table_name="roles")
    op.drop_index(op.f("ix_roles_discord_role_id"), table_name="roles")
    op.drop_table("roles")

    op.drop_index(op.f("ix_guild_settings_guild_id"), table_name="guild_settings")
    op.drop_table("guild_settings")

    op.drop_index(op.f("ix_guild_members_user_id"), table_name="guild_members")
    op.drop_index(op.f("ix_guild_members_guild_id"), table_name="guild_members")
    op.drop_table("guild_members")

    op.drop_index(op.f("ix_guilds_discord_guild_id"), table_name="guilds")
    op.drop_table("guilds")

    op.drop_index(op.f("ix_users_discord_user_id"), table_name="users")
    op.drop_table("users")
