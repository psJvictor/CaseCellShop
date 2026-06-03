from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import AsyncSessionLocal, engine
from app.middleware.logging import LoggingMiddleware, configure_logging
from app.routers import cart, orders, products
from app.services.erp_sync import erp_sync_loop, sync_from_erp
from app.services.reservation_cleanup import cleanup_loop

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging()
    log.info("startup_begin")

    # Run initial ERP sync so the DB has data before we start serving traffic
    try:
        async with AsyncSessionLocal() as db:
            async with db.begin():
                count = await sync_from_erp(db)
                log.info("initial_sync_complete", products_synced=count)
    except Exception:
        log.exception("initial_sync_failed_continuing")

    # Start background tasks
    sync_task = asyncio.create_task(erp_sync_loop())
    clean_task = asyncio.create_task(cleanup_loop())

    yield

    # Graceful shutdown
    sync_task.cancel()
    clean_task.cancel()
    await asyncio.gather(sync_task, clean_task, return_exceptions=True)
    await engine.dispose()
    log.info("shutdown_complete")


app = FastAPI(
    title="CaseCellShop API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(LoggingMiddleware)

app.include_router(products.router)
app.include_router(cart.router, prefix="/api/cart")
app.include_router(orders.router, prefix="/api/orders")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
