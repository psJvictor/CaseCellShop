from __future__ import annotations

import uuid
from decimal import Decimal
from uuid import UUID

import structlog
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cart import Cart, CartItem
from app.models.product import Product
from app.models.reservation import Reservation
from app.schemas.cart import CartDetailOut, CartItemOut, CartOut
from app.services.stock_service import release_stock, reserve_stock

log = structlog.get_logger()


async def get_or_create_cart(session_id: str | None, db: AsyncSession) -> Cart:
    """Return existing cart for session_id, or create a new one."""
    if session_id:
        row = await db.execute(select(Cart).where(Cart.session_id == session_id))
        cart = row.scalar_one_or_none()
        if cart:
            return cart

    # Create a new cart — generate session_id if not provided
    new_session_id = session_id if session_id else str(uuid.uuid4())
    cart = Cart(session_id=new_session_id)
    db.add(cart)
    await db.flush()
    log.info("cart_created", session_id=new_session_id, cart_id=str(cart.id))
    return cart


async def get_cart_detail(session_id: str, db: AsyncSession) -> CartDetailOut:
    """Return full cart detail including items, prices and reservations."""
    cart_row = await db.execute(select(Cart).where(Cart.session_id == session_id))
    cart = cart_row.scalar_one_or_none()
    if cart is None:
        raise HTTPException(status_code=404, detail="Carrinho não encontrado")

    # Fetch cart items joined with products
    items_row = await db.execute(
        select(CartItem, Product)
        .join(Product, CartItem.product_id == Product.id)
        .where(CartItem.cart_id == cart.id)
    )
    cart_items = items_row.all()

    # Fetch active reservations for this cart
    res_row = await db.execute(
        select(Reservation).where(
            Reservation.cart_id == cart.id,
            Reservation.status == "active",
        )
    )
    reservations = {r.product_id: r for r in res_row.scalars().all()}

    items_out: list[CartItemOut] = []
    total_amount = Decimal("0")

    for cart_item, product in cart_items:
        res = reservations.get(product.id)
        item_total = Decimal(str(product.price)) * cart_item.quantity
        total_amount += item_total

        items_out.append(
            CartItemOut(
                cart_item_id=cart_item.id,
                product_id=product.id,
                product_name=product.name,
                quantity=cart_item.quantity,
                unit_price=product.price,
                reservation_id=res.id if res else None,
                expires_at=res.expires_at if res else None,
            )
        )

    return CartDetailOut(
        cart_id=cart.id,
        session_id=cart.session_id,
        items=items_out,
        total_amount=total_amount,
    )


async def add_to_cart(
    session_id: str,
    product_id: UUID,
    quantity: int,
    db: AsyncSession,
) -> dict:
    """Add or update a product in the cart, reserving stock atomically."""
    # Ensure product exists
    product_row = await db.execute(select(Product).where(Product.id == product_id))
    product = product_row.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    # Get or create cart
    cart = await get_or_create_cart(session_id, db)

    # Reserve stock (uses SELECT FOR UPDATE internally)
    reservation = await reserve_stock(
        product_id=product_id,
        cart_id=cart.id,
        quantity=quantity,
        db=db,
    )

    # Upsert cart item
    existing_item_row = await db.execute(
        select(CartItem).where(
            CartItem.cart_id == cart.id,
            CartItem.product_id == product_id,
        )
    )
    existing_item = existing_item_row.scalar_one_or_none()

    if existing_item:
        existing_item.quantity = quantity
        cart_item = existing_item
    else:
        cart_item = CartItem(
            cart_id=cart.id,
            product_id=product_id,
            quantity=quantity,
        )
        db.add(cart_item)

    await db.flush()
    log.info(
        "cart_item_added",
        session_id=session_id,
        product_id=str(product_id),
        quantity=quantity,
    )

    return {
        "cart_id": str(cart.id),
        "session_id": cart.session_id,
        "product_id": str(product_id),
        "quantity": quantity,
        "reservation_id": str(reservation.id),
        "expires_at": reservation.expires_at.isoformat(),
    }


async def remove_from_cart(
    session_id: str,
    product_id: UUID,
    db: AsyncSession,
) -> None:
    """Remove an item from the cart and release its stock reservation."""
    cart_row = await db.execute(select(Cart).where(Cart.session_id == session_id))
    cart = cart_row.scalar_one_or_none()
    if cart is None:
        raise HTTPException(status_code=404, detail="Carrinho não encontrado")

    # Release the stock reservation
    await release_stock(product_id=product_id, cart_id=cart.id, db=db)

    # Delete the cart item
    await db.execute(
        delete(CartItem).where(
            CartItem.cart_id == cart.id,
            CartItem.product_id == product_id,
        )
    )
    await db.flush()
    log.info(
        "cart_item_removed",
        session_id=session_id,
        product_id=str(product_id),
    )
