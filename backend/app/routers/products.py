from __future__ import annotations

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.product import Product, Stock
from app.schemas.product import ProductListOut, ProductOut

log = structlog.get_logger()
router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("", response_model=ProductListOut)
async def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    model_compat: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> ProductListOut:
    query = select(Product, Stock).join(Stock, Product.id == Stock.product_id)
    if model_compat:
        query = query.where(Product.model_compat.ilike(f"%{model_compat}%"))

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar_one()

    query = query.offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(query)).all()

    items = [
        ProductOut(
            id=product.id,
            erp_id=product.erp_id,
            name=product.name,
            description=product.description,
            price=product.price,
            image_url=product.image_url,
            model_compat=product.model_compat,
            stock_available=stock.quantity_available,
            last_synced_at=product.last_synced_at,
        )
        for product, stock in rows
    ]

    log.info("products_listed", count=len(items), page=page)
    return ProductListOut(items=items, total=total, page=page, page_size=page_size)


@router.get("/{product_id}", response_model=ProductOut)
async def get_product(
    product_id: str,
    db: AsyncSession = Depends(get_db),
) -> ProductOut:
    try:
        pid = UUID(product_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    row = (
        await db.execute(
            select(Product, Stock)
            .join(Stock, Product.id == Stock.product_id)
            .where(Product.id == pid)
        )
    ).first()

    if row is None:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    product, stock = row
    return ProductOut(
        id=product.id,
        erp_id=product.erp_id,
        name=product.name,
        description=product.description,
        price=product.price,
        image_url=product.image_url,
        model_compat=product.model_compat,
        stock_available=stock.quantity_available,
        last_synced_at=product.last_synced_at,
    )
