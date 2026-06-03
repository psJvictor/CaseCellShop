from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Stock
from app.models.reservation import Reservation
from app.services.reservation_cleanup import cleanup_expired_reservations
from app.services.stock_service import StockInsufficientError, release_stock, reserve_stock


@pytest.mark.asyncio
async def test_reserve_stock_success(create_product, db_session: AsyncSession):
    """Reserving 3 units from 10-unit stock leaves available=7, reserved=3."""
    product = await create_product(stock=10)
    import uuid
    cart_id = uuid.uuid4()

    reservation = await reserve_stock(product.id, cart_id, 3, db_session)

    assert reservation.quantity == 3
    assert reservation.status == "active"

    stock = (
        await db_session.execute(select(Stock).where(Stock.product_id == product.id))
    ).scalar_one()
    assert stock.quantity_available == 7
    assert stock.quantity_reserved == 3


@pytest.mark.asyncio
async def test_reserve_insufficient_stock(create_product, db_session: AsyncSession):
    """Attempting to reserve 11 units from 10 raises StockInsufficientError (HTTP 409)."""
    product = await create_product(stock=10)
    import uuid
    cart_id = uuid.uuid4()

    with pytest.raises(StockInsufficientError) as exc_info:
        await reserve_stock(product.id, cart_id, 11, db_session)

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_reserve_zero_stock(create_product, db_session: AsyncSession):
    """Attempting to reserve from zero-stock product raises StockInsufficientError."""
    product = await create_product(stock=0)
    import uuid
    cart_id = uuid.uuid4()

    with pytest.raises(StockInsufficientError) as exc_info:
        await reserve_stock(product.id, cart_id, 1, db_session)

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_reserve_updates_existing_reservation(create_product, db_session: AsyncSession):
    """Reserving 2 then updating to 3 results in total reserved=3 (not 5)."""
    product = await create_product(stock=10)
    import uuid
    cart_id = uuid.uuid4()

    # First reservation: 2 units
    res1 = await reserve_stock(product.id, cart_id, 2, db_session)
    assert res1.quantity == 2

    # Update to 3 units — should be treated as delta of +1
    res2 = await reserve_stock(product.id, cart_id, 3, db_session)
    assert res2.id == res1.id  # same reservation row updated
    assert res2.quantity == 3

    stock = (
        await db_session.execute(select(Stock).where(Stock.product_id == product.id))
    ).scalar_one()
    assert stock.quantity_available == 7   # 10 - 3
    assert stock.quantity_reserved == 3    # exactly 3, not 5


@pytest.mark.asyncio
async def test_release_stock(create_product, db_session: AsyncSession):
    """After reserving 3 and releasing, available returns to original 10."""
    product = await create_product(stock=10)
    import uuid
    cart_id = uuid.uuid4()

    await reserve_stock(product.id, cart_id, 3, db_session)

    # Verify reserved
    stock = (
        await db_session.execute(select(Stock).where(Stock.product_id == product.id))
    ).scalar_one()
    assert stock.quantity_available == 7

    await release_stock(product.id, cart_id, db_session)

    # Verify restored
    await db_session.refresh(stock)
    assert stock.quantity_available == 10
    assert stock.quantity_reserved == 0

    # Reservation should be marked released
    reservation = (
        await db_session.execute(
            select(Reservation).where(
                Reservation.cart_id == cart_id,
                Reservation.product_id == product.id,
            )
        )
    ).scalar_one()
    assert reservation.status == "released"


@pytest.mark.asyncio
async def test_cleanup_expired_reservations(create_product, db_session: AsyncSession):
    """Expired active reservations are released and stock is restored."""
    product = await create_product(stock=10)
    import uuid
    cart_id = uuid.uuid4()

    # Create an already-expired reservation manually
    expired_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    reservation = Reservation(
        cart_id=cart_id,
        product_id=product.id,
        quantity=4,
        status="active",
        expires_at=expired_at,
    )
    db_session.add(reservation)

    # Reduce stock manually to simulate it was reserved
    stock = (
        await db_session.execute(select(Stock).where(Stock.product_id == product.id))
    ).scalar_one()
    stock.quantity_available -= 4
    stock.quantity_reserved += 4
    await db_session.flush()

    assert stock.quantity_available == 6

    # Run cleanup
    count = await cleanup_expired_reservations(db_session)
    assert count == 1

    # Stock should be restored
    await db_session.refresh(stock)
    assert stock.quantity_available == 10
    assert stock.quantity_reserved == 0

    # Reservation should be released
    await db_session.refresh(reservation)
    assert reservation.status == "released"
