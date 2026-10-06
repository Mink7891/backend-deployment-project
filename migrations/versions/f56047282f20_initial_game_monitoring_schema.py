"""Initial game monitoring schema

Revision ID: f56047282f20
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "f56047282f20"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "games",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("steam_app_id", sa.String(length=32), nullable=True),
        sa.Column("thumbnail_url", sa.String(length=2048), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("cheapest_price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "watchlists",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "offers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.String(length=32), nullable=False),
        sa.Column("deal_id", sa.String(length=512), nullable=False),
        sa.Column("store_id", sa.String(length=32), nullable=False),
        sa.Column("price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("retail_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("savings", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("game_id", "deal_id"),
    )
    op.create_index(op.f("ix_offers_game_id"), "offers", ["game_id"], unique=False)
    op.create_table(
        "price_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.String(length=32), nullable=False),
        sa.Column("store_id", sa.String(length=32), nullable=False),
        sa.Column("deal_id", sa.String(length=512), nullable=False),
        sa.Column("price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_price_snapshots_game_observed",
        "price_snapshots",
        ["game_id", "observed_at"],
        unique=False,
    )
    op.create_table(
        "watchlist_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("watchlist_id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.String(length=32), nullable=False),
        sa.Column("target_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("steam_only", sa.Boolean(), nullable=False),
        sa.Column("alert_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["game_id"],
            ["games.id"],
        ),
        sa.ForeignKeyConstraint(["watchlist_id"], ["watchlists.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("watchlist_id", "game_id"),
    )
    op.create_index(
        op.f("ix_watchlist_items_game_id"), "watchlist_items", ["game_id"], unique=False
    )
    op.create_index(
        op.f("ix_watchlist_items_watchlist_id"), "watchlist_items", ["watchlist_id"], unique=False
    )
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("watchlist_id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=True),
        sa.Column("game_id", sa.String(length=32), nullable=False),
        sa.Column("game_title", sa.String(length=300), nullable=False),
        sa.Column("target_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("observed_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["game_id"],
            ["games.id"],
        ),
        sa.ForeignKeyConstraint(["item_id"], ["watchlist_items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["watchlist_id"], ["watchlists.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notifications_watchlist_created",
        "notifications",
        ["watchlist_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_watchlist_created", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index(op.f("ix_watchlist_items_watchlist_id"), table_name="watchlist_items")
    op.drop_index(op.f("ix_watchlist_items_game_id"), table_name="watchlist_items")
    op.drop_table("watchlist_items")
    op.drop_index("ix_price_snapshots_game_observed", table_name="price_snapshots")
    op.drop_table("price_snapshots")
    op.drop_index(op.f("ix_offers_game_id"), table_name="offers")
    op.drop_table("offers")
    op.drop_table("watchlists")
    op.drop_table("games")
