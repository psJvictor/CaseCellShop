from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProductOut(BaseModel):
    id: UUID
    erp_id: str
    name: str
    description: str | None
    price: Decimal
    image_url: str | None
    model_compat: str | None
    stock_available: int
    last_synced_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductListOut(BaseModel):
    items: list[ProductOut]
    total: int
    page: int
    page_size: int
