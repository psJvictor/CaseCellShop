from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class CartCreate(BaseModel):
    session_id: str | None = None


class CartOut(BaseModel):
    cart_id: UUID
    session_id: str


class CartItemAdd(BaseModel):
    product_id: UUID
    quantity: int = Field(gt=0, le=100)


class CartItemOut(BaseModel):
    cart_item_id: UUID
    product_id: UUID
    product_name: str
    quantity: int
    unit_price: Decimal
    reservation_id: UUID | None
    expires_at: datetime | None


class CartDetailOut(BaseModel):
    cart_id: UUID
    session_id: str
    items: list[CartItemOut]
    total_amount: Decimal
