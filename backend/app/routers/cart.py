from __future__ import annotations

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.cart import CartCreate, CartDetailOut, CartItemAdd, CartOut
from app.services.cart_service import (
    add_to_cart,
    get_cart_detail,
    get_or_create_cart,
    remove_from_cart,
)

log = structlog.get_logger()
router = APIRouter(tags=["cart"])


@router.post("", response_model=CartOut, status_code=201)
async def create_cart(
    body: CartCreate,
    db: AsyncSession = Depends(get_db),
) -> CartOut:
    """Create a new cart (or return existing one if session_id is provided)."""
    async with db.begin():
        cart = await get_or_create_cart(body.session_id, db)

    log.info("cart_endpoint_created", cart_id=str(cart.id), session_id=cart.session_id)
    return CartOut(cart_id=cart.id, session_id=cart.session_id)


@router.get("/{session_id}", response_model=CartDetailOut)
async def get_cart(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> CartDetailOut:
    """Get full cart detail including items and reservations."""
    return await get_cart_detail(session_id, db)


@router.post("/{session_id}/items", response_model=dict, status_code=201)
async def add_item(
    session_id: str,
    body: CartItemAdd,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Add or update an item in the cart. Reserves stock atomically."""
    async with db.begin():
        result = await add_to_cart(
            session_id=session_id,
            product_id=body.product_id,
            quantity=body.quantity,
            db=db,
        )
    return result


@router.delete("/{session_id}/items/{product_id}", status_code=204)
async def remove_item(
    session_id: str,
    product_id: str,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Remove an item from the cart and release its stock reservation."""
    try:
        pid = UUID(product_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="product_id inválido")

    async with db.begin():
        await remove_from_cart(
            session_id=session_id,
            product_id=pid,
            db=db,
        )

    return Response(status_code=204)
