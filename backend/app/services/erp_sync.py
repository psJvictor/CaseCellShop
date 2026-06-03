from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.product import Product, Stock
from app.services.erp_service import CircuitOpenError, get_erp_service

log = structlog.get_logger()


async def sync_from_erp(db: AsyncSession) -> int:
    """Sync products from ERP into our database.

    Performs an upsert on products keyed by erp_id, then updates stock
    levels while respecting any currently reserved quantities.

    Returns the number of products synced.
    """
    erp = get_erp_service()
    products_data = await erp.get_products()

    now = datetime.now(timezone.utc)
    count = 0

    for pd in products_data:
        # Upsert product — update all fields on conflict
        stmt = (
            pg_insert(Product)
            .values(
                erp_id=pd["erp_id"],
                name=pd["name"],
                description=pd.get("description"),
                price=pd["price"],
                image_url=pd.get("image_url"),
                model_compat=pd.get("model_compat"),
                last_synced_at=now,
            )
            .on_conflict_do_update(
                index_elements=["erp_id"],
                set_={
                    "name": pd["name"],
                    "description": pd.get("description"),
                    "price": pd["price"],
                    "image_url": pd.get("image_url"),
                    "model_compat": pd.get("model_compat"),
                    "last_synced_at": now,
                },
            )
            .returning(Product.id)
        )

        result = await db.execute(stmt)
        product_id = result.scalar_one()

        # Upsert stock — preserve reserved quantity, adjust available accordingly
        erp_qty = pd.get("stock", 0)

        existing_stock_row = await db.execute(
            select(Stock).where(Stock.product_id == product_id)
        )
        existing = existing_stock_row.scalar_one_or_none()

        if existing is None:
            db.add(
                Stock(
                    product_id=product_id,
                    quantity_available=erp_qty,
                    quantity_reserved=0,
                )
            )
        else:
            # Don't reduce available below 0 after accounting for reservations
            new_available = max(0, erp_qty - existing.quantity_reserved)
            existing.quantity_available = new_available
            existing.updated_at = now

        count += 1

    return count


async def erp_sync_loop() -> None:
    """Background task: sync ERP every ERP_SYNC_INTERVAL_SECONDS."""
    log.info("erp_sync_loop_started", interval=settings.ERP_SYNC_INTERVAL_SECONDS)
    while True:
        await asyncio.sleep(settings.ERP_SYNC_INTERVAL_SECONDS)
        try:
            async with AsyncSessionLocal() as db:
                async with db.begin():
                    count = await sync_from_erp(db)
            log.info("erp_sync_success", products_synced=count)
        except CircuitOpenError:
            log.warning("erp_sync_circuit_open")
        except Exception:
            log.exception("erp_sync_failed")
