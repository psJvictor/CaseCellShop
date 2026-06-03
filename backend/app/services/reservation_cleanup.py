from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.product import Stock
from app.models.reservation import Reservation

log = structlog.get_logger()


async def cleanup_expired_reservations(db: AsyncSession) -> int:
    """Release expired reservations back to available stock.

    Returns the count of reservations that were released.
    Uses SKIP LOCKED so multiple instances don't deadlock on the same rows.
    """
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(Reservation)
        .where(Reservation.status == "active", Reservation.expires_at < now)
        .with_for_update(skip_locked=True)
    )
    expired = result.scalars().all()

    for reservation in expired:
        await db.execute(
            update(Stock)
            .where(Stock.product_id == reservation.product_id)
            .values(
                quantity_available=Stock.quantity_available + reservation.quantity,
                quantity_reserved=Stock.quantity_reserved - reservation.quantity,
            )
        )
        reservation.status = "released"

    if expired:
        log.info("reservations_cleaned_up", count=len(expired))

    return len(expired)


async def cleanup_loop() -> None:
    """Background task: release expired reservations every CLEANUP_INTERVAL_SECONDS."""
    log.info("cleanup_loop_started", interval=settings.CLEANUP_INTERVAL_SECONDS)
    while True:
        await asyncio.sleep(settings.CLEANUP_INTERVAL_SECONDS)
        try:
            async with AsyncSessionLocal() as db:
                async with db.begin():
                    count = await cleanup_expired_reservations(db)
                    if count > 0:
                        log.info("cleanup_loop_ran", released=count)
        except Exception:
            log.exception("cleanup_loop_error")
