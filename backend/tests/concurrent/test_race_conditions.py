from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models.cart import Cart
from app.models.product import Product, Stock

TEST_DB_URL = settings.TEST_DATABASE_URL


@pytest_asyncio.fixture(scope="module")
async def concurrent_engine():
    """Separate engine for concurrent tests to avoid interference with unit tests."""
    engine = create_async_engine(TEST_DB_URL, echo=False, pool_size=20, max_overflow=10)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def _setup_product_with_stock(
    engine, stock: int = 1, price: Decimal = Decimal("29.90")
) -> Product:
    """Create a product + stock row for concurrent tests."""
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db:
        async with db.begin():
            product = Product(
                erp_id=f"CONC-{uuid.uuid4().hex[:8].upper()}",
                name="Concurrent Test Product",
                price=price,
            )
            db.add(product)
            await db.flush()
            db.add(Stock(product_id=product.id, quantity_available=stock, quantity_reserved=0))
            await db.flush()
            return product


async def _setup_cart(engine, session_id: str) -> Cart:
    """Create a cart for concurrent tests."""
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db:
        async with db.begin():
            cart = Cart(session_id=session_id)
            db.add(cart)
            await db.flush()
            return cart


@pytest.mark.asyncio
async def test_no_overselling_last_unit(concurrent_engine):
    """20 concurrent add-to-cart requests for a 1-unit product.
    Exactly 1 should succeed (201), 19 should get 409.
    """
    STOCK_QTY = 1
    CONCURRENT = 20

    product = await _setup_product_with_stock(concurrent_engine, stock=STOCK_QTY)

    # Create all session IDs and carts up front
    session_ids = [str(uuid.uuid4()) for _ in range(CONCURRENT)]
    for sid in session_ids:
        await _setup_cart(concurrent_engine, sid)

    # Each coroutine uses its own independent DB session (simulating separate HTTP connections)
    async def make_request(session_id: str) -> int:
        session_factory = async_sessionmaker(
            concurrent_engine, expire_on_commit=False
        )

        async def get_test_db():
            async with session_factory() as s:
                yield s

        app.dependency_overrides[get_db] = get_test_db
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            resp = await c.post(
                f"/api/cart/{session_id}/items",
                json={"product_id": str(product.id), "quantity": 1},
            )
            return resp.status_code

    status_codes = await asyncio.gather(*[make_request(sid) for sid in session_ids])
    app.dependency_overrides.clear()

    successes = [s for s in status_codes if s == 201]
    conflicts = [s for s in status_codes if s == 409]

    assert len(successes) == STOCK_QTY, (
        f"Expected exactly {STOCK_QTY} success(es) but got {len(successes)}"
    )
    assert len(conflicts) == CONCURRENT - STOCK_QTY

    # Verify database integrity — stock numbers must add up correctly
    session_factory = async_sessionmaker(concurrent_engine, expire_on_commit=False)
    async with session_factory() as verify_db:
        stock = (
            await verify_db.execute(
                select(Stock).where(Stock.product_id == product.id)
            )
        ).scalar_one()
        assert stock.quantity_available == 0
        assert stock.quantity_reserved == STOCK_QTY


@pytest.mark.asyncio
async def test_no_overselling_concurrent_checkout(concurrent_engine):
    """Two users with the same product reserved both try to checkout simultaneously.
    Both should succeed because each has their own reservation for 1 unit of a 2-unit product.
    """
    product = await _setup_product_with_stock(concurrent_engine, stock=2)

    session_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    for sid in session_ids:
        await _setup_cart(concurrent_engine, sid)

    # Add item to each cart sequentially to acquire reservations
    session_factory = async_sessionmaker(concurrent_engine, expire_on_commit=False)

    for sid in session_ids:
        async def get_test_db_factory(sf=session_factory):
            async with sf() as s:
                yield s

        app.dependency_overrides[get_db] = get_test_db_factory
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            resp = await c.post(
                f"/api/cart/{sid}/items",
                json={"product_id": str(product.id), "quantity": 1},
            )
            assert resp.status_code == 201

    # Now both checkout simultaneously
    async def do_checkout(session_id: str) -> int:
        sf = async_sessionmaker(concurrent_engine, expire_on_commit=False)

        async def get_test_db():
            async with sf() as s:
                yield s

        app.dependency_overrides[get_db] = get_test_db
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            resp = await c.post(
                "/api/orders/checkout",
                json={
                    "idempotency_key": str(uuid.uuid4()),
                    "session_id": session_id,
                    "customer_name": "Test User",
                    "customer_email": "test@example.com",
                    "customer_address": "Rua Test, 1, Cidade, Estado",
                },
            )
            return resp.status_code

    statuses = await asyncio.gather(*[do_checkout(sid) for sid in session_ids])
    app.dependency_overrides.clear()

    # Both should succeed since each has their own reservation
    assert all(s == 201 for s in statuses), f"Expected both 201 but got {statuses}"

    # Final stock: 2 units sold, 0 reserved, 0 available
    session_factory2 = async_sessionmaker(concurrent_engine, expire_on_commit=False)
    async with session_factory2() as verify_db:
        stock = (
            await verify_db.execute(
                select(Stock).where(Stock.product_id == product.id)
            )
        ).scalar_one()
        assert stock.quantity_reserved == 0
        assert stock.quantity_available == 0


@pytest.mark.asyncio
async def test_concurrent_different_products(concurrent_engine):
    """Multiple users buying different products concurrently should all succeed."""
    NUM_PRODUCTS = 5

    products = []
    for _ in range(NUM_PRODUCTS):
        p = await _setup_product_with_stock(concurrent_engine, stock=5)
        products.append(p)

    session_ids = [str(uuid.uuid4()) for _ in range(NUM_PRODUCTS)]
    for sid in session_ids:
        await _setup_cart(concurrent_engine, sid)

    async def add_and_checkout(session_id: str, product: Product) -> tuple[int, int]:
        sf = async_sessionmaker(concurrent_engine, expire_on_commit=False)

        async def get_test_db():
            async with sf() as s:
                yield s

        app.dependency_overrides[get_db] = get_test_db
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            add_resp = await c.post(
                f"/api/cart/{session_id}/items",
                json={"product_id": str(product.id), "quantity": 2},
            )
            if add_resp.status_code != 201:
                return add_resp.status_code, 0

            checkout_resp = await c.post(
                "/api/orders/checkout",
                json={
                    "idempotency_key": str(uuid.uuid4()),
                    "session_id": session_id,
                    "customer_name": "User Test",
                    "customer_email": "user@test.com",
                    "customer_address": "Rua Concurrent, 1, Cidade, Estado",
                },
            )
            return add_resp.status_code, checkout_resp.status_code

    results = await asyncio.gather(
        *[add_and_checkout(sid, prod) for sid, prod in zip(session_ids, products)]
    )
    app.dependency_overrides.clear()

    add_statuses = [r[0] for r in results]
    checkout_statuses = [r[1] for r in results]

    assert all(s == 201 for s in add_statuses), f"Add failures: {add_statuses}"
    assert all(s == 201 for s in checkout_statuses), f"Checkout failures: {checkout_statuses}"
