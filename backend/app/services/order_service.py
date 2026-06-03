from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

import structlog
from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cart import Cart, CartItem
from app.models.order import Order, OrderItem
from app.models.product import Product, Stock
from app.models.reservation import Reservation
from app.schemas.order import CheckoutRequest, OrderItemOut, OrderOut

log = structlog.get_logger()


async def _build_order_out(order: Order, db: AsyncSession) -> OrderOut:
    """Build an OrderOut schema from an Order ORM object."""
    items_row = await db.execute(
        select(OrderItem, Product)
        .join(Product, OrderItem.product_id == Product.id)
        .where(OrderItem.order_id == order.id)
    )
    items = items_row.all()

    order_items_out = [
        OrderItemOut(
            product_name=product.name,
            quantity=item.quantity,
            unit_price=item.unit_price,
        )
        for item, product in items
    ]

    return OrderOut(
        order_id=order.id,
        status=order.status,
        customer_name=order.customer_name,
        customer_email=order.customer_email,
        total_amount=order.total_amount,
        items=order_items_out,
        created_at=order.created_at,
    )


async def checkout(
    request: CheckoutRequest,
    db: AsyncSession,
) -> tuple[OrderOut, int]:
    """Process checkout. Returns (order, http_status_code).
    200 if idempotent replay, 201 if new order created.
    """
    log.info(
        "checkout_attempt",
        idempotency_key=request.idempotency_key,
        session_id=request.session_id,
    )

    # Fast idempotency check — return existing order if key already used
    existing_row = await db.execute(
        select(Order).where(Order.idempotency_key == request.idempotency_key)
    )
    existing_order = existing_row.scalar_one_or_none()
    if existing_order:
        log.info("checkout_idempotent_replay", order_id=str(existing_order.id))
        return await _build_order_out(existing_order, db), 200

    # Get the cart
    cart_row = await db.execute(
        select(Cart).where(Cart.session_id == request.session_id)
    )
    cart = cart_row.scalar_one_or_none()
    if cart is None:
        raise HTTPException(status_code=404, detail="Carrinho não encontrado")

    # Get cart items joined with products
    items_row = await db.execute(
        select(CartItem, Product)
        .join(Product, CartItem.product_id == Product.id)
        .where(CartItem.cart_id == cart.id)
    )
    cart_items = items_row.all()
    if not cart_items:
        raise HTTPException(status_code=400, detail="Carrinho vazio")

    # Lock all reservations + stock in deterministic order (by product_id) to prevent deadlocks
    product_ids = sorted([ci.product_id for ci, _ in cart_items])

    now = datetime.now(timezone.utc)
    reservations: dict[UUID, Reservation] = {}

    for pid in product_ids:
        res_row = await db.execute(
            select(Reservation)
            .where(
                Reservation.cart_id == cart.id,
                Reservation.product_id == pid,
                Reservation.status == "active",
            )
            .with_for_update()
        )
        res = res_row.scalar_one_or_none()
        if res is None or res.expires_at < now:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Reserva expirada ou não encontrada para produto {pid}. "
                    "Adicione ao carrinho novamente."
                ),
            )
        reservations[pid] = res

        # Acquire stock lock in same order to prevent deadlocks
        await db.execute(
            select(Stock).where(Stock.product_id == pid).with_for_update()
        )

    # Calculate total amount
    total = sum(
        Decimal(str(product.price)) * cart_item.quantity
        for cart_item, product in cart_items
    )

    # Create the order
    order = Order(
        cart_id=cart.id,
        idempotency_key=request.idempotency_key,
        status="confirmed",
        customer_name=request.customer_name,
        customer_email=request.customer_email,
        customer_address=request.customer_address,
        total_amount=total,
    )
    db.add(order)
    await db.flush()  # Get the order.id populated

    # Create order items and confirm reservations
    for cart_item, product in cart_items:
        db.add(
            OrderItem(
                order_id=order.id,
                product_id=product.id,
                quantity=cart_item.quantity,
                unit_price=product.price,
            )
        )
        res = reservations[product.id]
        res.status = "confirmed"

        # Convert reserved stock to sold (decrement reserved, leave available unchanged)
        await db.execute(
            update(Stock)
            .where(Stock.product_id == product.id)
            .values(
                quantity_reserved=Stock.quantity_reserved - cart_item.quantity,
                updated_at=now,
            )
        )

    await db.flush()
    log.info("checkout_success", order_id=str(order.id), total=str(total))
    return await _build_order_out(order, db), 201


async def get_order_by_id(order_id: UUID, db: AsyncSession) -> OrderOut:
    """Retrieve an order by its ID."""
    order_row = await db.execute(select(Order).where(Order.id == order_id))
    order = order_row.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    return await _build_order_out(order, db)
