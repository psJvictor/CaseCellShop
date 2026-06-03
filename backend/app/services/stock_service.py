from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import structlog
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.product import Stock
from app.models.reservation import Reservation

log = structlog.get_logger()


class StockInsufficientError(HTTPException):
    def __init__(self, available: int) -> None:
        super().__init__(
            status_code=409,
            detail=f"Estoque insuficiente. Disponível: {available}",
        )
        self.available = available


async def reserve_stock(
    product_id: UUID,
    cart_id: UUID,
    quantity: int,
    db: AsyncSession,
) -> Reservation:
    """Reserve stock for a cart item. Uses SELECT FOR UPDATE to prevent overselling."""
    log.info(
        "stock_reserve_attempt",
        product_id=str(product_id),
        cart_id=str(cart_id),
        quantity=quantity,
    )

    # Lock the stock row first — prevents concurrent overselling
    stock_row = await db.execute(
        select(Stock).where(Stock.product_id == product_id).with_for_update()
    )
    stock = stock_row.scalar_one_or_none()
    if stock is None:
        raise HTTPException(status_code=404, detail="Estoque não encontrado para este produto")

    # Check for existing active reservation for this cart+product
    existing_res_row = await db.execute(
        select(Reservation).where(
            Reservation.cart_id == cart_id,
            Reservation.product_id == product_id,
            Reservation.status == "active",
        )
    )
    existing_res = existing_res_row.scalar_one_or_none()

    if existing_res:
        # Calculate delta: how much MORE stock we need (can be negative if reducing qty)
        delta = quantity - existing_res.quantity
    else:
        delta = quantity

    # Check availability — only need `delta` additional units from available pool
    if stock.quantity_available < delta:
        available = stock.quantity_available + (existing_res.quantity if existing_res else 0)
        log.warning(
            "stock_insufficient",
            product_id=str(product_id),
            available=stock.quantity_available,
            requested=quantity,
        )
        raise StockInsufficientError(available=available)

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.RESERVATION_TTL_MINUTES)

    if existing_res:
        existing_res.quantity = quantity
        existing_res.expires_at = expires_at
        reservation = existing_res
    else:
        reservation = Reservation(
            cart_id=cart_id,
            product_id=product_id,
            quantity=quantity,
            expires_at=expires_at,
            status="active",
        )
        db.add(reservation)

    # Update stock atomically within this locked transaction
    stock.quantity_available -= delta
    stock.quantity_reserved += delta
    stock.updated_at = datetime.now(timezone.utc)

    await db.flush()
    log.info(
        "stock_reserved",
        product_id=str(product_id),
        delta=delta,
        quantity_available=stock.quantity_available,
    )
    return reservation


async def release_stock(
    product_id: UUID,
    cart_id: UUID,
    db: AsyncSession,
) -> None:
    """Release a reservation (e.g., when removing from cart)."""
    res_row = await db.execute(
        select(Reservation)
        .where(
            Reservation.cart_id == cart_id,
            Reservation.product_id == product_id,
            Reservation.status == "active",
        )
        .with_for_update()
    )
    reservation = res_row.scalar_one_or_none()
    if reservation is None:
        return

    stock_row = await db.execute(
        select(Stock).where(Stock.product_id == product_id).with_for_update()
    )
    stock = stock_row.scalar_one_or_none()
    if stock:
        stock.quantity_available += reservation.quantity
        stock.quantity_reserved -= reservation.quantity
        stock.updated_at = datetime.now(timezone.utc)

    reservation.status = "released"
    await db.flush()
    log.info(
        "stock_released",
        product_id=str(product_id),
        quantity=reservation.quantity,
    )
