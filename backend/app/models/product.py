from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    NUMERIC,
    TEXT,
    VARCHAR,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.cart import CartItem
    from app.models.reservation import Reservation
    from app.models.order import OrderItem


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    erp_id: Mapped[str] = mapped_column(VARCHAR(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(VARCHAR(255), nullable=False)
    description: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    price: Mapped[Decimal] = mapped_column(NUMERIC(10, 2), nullable=False)
    image_url: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    model_compat: Mapped[str | None] = mapped_column(VARCHAR(255), nullable=True)
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    stock: Mapped[Stock] = relationship("Stock", back_populates="product", uselist=False)
    cart_items: Mapped[list[CartItem]] = relationship("CartItem", back_populates="product")
    reservations: Mapped[list[Reservation]] = relationship(
        "Reservation", back_populates="product"
    )
    order_items: Mapped[list[OrderItem]] = relationship(
        "OrderItem", back_populates="product"
    )


class Stock(Base):
    __tablename__ = "stock"
    __table_args__ = (
        CheckConstraint("quantity_available >= 0", name="stock_available_non_negative"),
        CheckConstraint("quantity_reserved >= 0", name="stock_reserved_non_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    quantity_available: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quantity_reserved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    product: Mapped[Product] = relationship("Product", back_populates="stock")
