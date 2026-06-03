from __future__ import annotations

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.order import CheckoutRequest, OrderOut
from app.services.order_service import checkout, get_order_by_id

log = structlog.get_logger()
router = APIRouter(tags=["orders"])


@router.post("/checkout")
async def checkout_endpoint(
    request: CheckoutRequest,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Process checkout. Returns 201 for new orders, 200 for idempotent replays."""
    async with db.begin():
        order_out, status_code = await checkout(request, db)

    return JSONResponse(
        content=order_out.model_dump(mode="json"),
        status_code=status_code,
    )


@router.get("/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: str,
    db: AsyncSession = Depends(get_db),
) -> OrderOut:
    """Retrieve an order by ID."""
    try:
        oid = UUID(order_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")

    return await get_order_by_id(oid, db)
