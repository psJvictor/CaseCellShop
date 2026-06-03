"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # products table
    op.create_table(
        "products",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("erp_id", sa.VARCHAR(64), nullable=False),
        sa.Column("name", sa.VARCHAR(255), nullable=False),
        sa.Column("description", sa.TEXT(), nullable=True),
        sa.Column("price", sa.NUMERIC(10, 2), nullable=False),
        sa.Column("image_url", sa.TEXT(), nullable=True),
        sa.Column("model_compat", sa.VARCHAR(255), nullable=True),
        sa.Column(
            "last_synced_at",
            sa.TIMESTAMP(timezone=True),
            server_default=text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("erp_id"),
    )

    # stock table
    op.create_table(
        "stock",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "quantity_available",
            sa.INTEGER(),
            server_default=text("0"),
            nullable=False,
        ),
        sa.Column(
            "quantity_reserved",
            sa.INTEGER(),
            server_default=text("0"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("quantity_available >= 0", name="stock_available_non_negative"),
        sa.CheckConstraint("quantity_reserved >= 0", name="stock_reserved_non_negative"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id"),
    )

    # carts table
    op.create_table(
        "carts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("session_id", sa.VARCHAR(128), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id"),
    )

    # cart_items table
    op.create_table(
        "cart_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("cart_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "quantity",
            sa.INTEGER(),
            server_default=text("1"),
            nullable=False,
        ),
        sa.Column(
            "added_at",
            sa.TIMESTAMP(timezone=True),
            server_default=text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("quantity > 0", name="cart_items_quantity_positive"),
        sa.ForeignKeyConstraint(["cart_id"], ["carts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cart_id", "product_id", name="uq_cart_items_cart_product"),
    )

    # reservations table
    op.create_table(
        "reservations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("cart_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity", sa.INTEGER(), nullable=False),
        sa.Column(
            "status",
            sa.VARCHAR(20),
            server_default=text("'active'"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("quantity > 0", name="reservations_quantity_positive"),
        sa.CheckConstraint(
            "status IN ('active', 'confirmed', 'released')",
            name="reservations_status_check",
        ),
        sa.ForeignKeyConstraint(["cart_id"], ["carts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cart_id", "product_id", name="uq_reservations_cart_product"),
    )

    # Create partial index on reservations expires_at for active reservations
    op.execute(
        "CREATE INDEX idx_reservations_expires ON reservations(expires_at) WHERE status = 'active'"
    )

    # orders table
    op.create_table(
        "orders",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("cart_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.VARCHAR(128), nullable=False),
        sa.Column(
            "status",
            sa.VARCHAR(20),
            server_default=text("'pending'"),
            nullable=False,
        ),
        sa.Column("customer_name", sa.VARCHAR(255), nullable=False),
        sa.Column("customer_email", sa.VARCHAR(255), nullable=False),
        sa.Column("customer_address", sa.TEXT(), nullable=False),
        sa.Column("total_amount", sa.NUMERIC(10, 2), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'confirmed', 'failed')",
            name="orders_status_check",
        ),
        sa.ForeignKeyConstraint(["cart_id"], ["carts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )

    # order_items table
    op.create_table(
        "order_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity", sa.INTEGER(), nullable=False),
        sa.Column("unit_price", sa.NUMERIC(10, 2), nullable=False),
        sa.CheckConstraint("quantity > 0", name="order_items_quantity_positive"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # erp_sync_log table
    op.create_table(
        "erp_sync_log",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.TIMESTAMP(timezone=True),
            server_default=text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.VARCHAR(20),
            server_default=text("'running'"),
            nullable=False,
        ),
        sa.Column(
            "products_synced",
            sa.INTEGER(),
            server_default=text("0"),
            nullable=True,
        ),
        sa.Column("error_message", sa.TEXT(), nullable=True),
        sa.CheckConstraint(
            "status IN ('running', 'success', 'failed')",
            name="erp_sync_log_status_check",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("erp_sync_log")
    op.drop_table("order_items")
    op.drop_table("orders")
    op.execute("DROP INDEX IF EXISTS idx_reservations_expires")
    op.drop_table("reservations")
    op.drop_table("cart_items")
    op.drop_table("carts")
    op.drop_table("stock")
    op.drop_table("products")
