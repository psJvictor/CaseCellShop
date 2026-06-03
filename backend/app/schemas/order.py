from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CheckoutRequest(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=128)
    session_id: str
    customer_name: str = Field(min_length=2, max_length=255)
    customer_email: EmailStr
    customer_address: str = Field(min_length=5, max_length=1000)


class OrderItemOut(BaseModel):
    product_name: str
    quantity: int
    unit_price: Decimal


class OrderOut(BaseModel):
    order_id: UUID
    status: str
    customer_name: str
    customer_email: str
    total_amount: Decimal
    items: list[OrderItemOut]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
