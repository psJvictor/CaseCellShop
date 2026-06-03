from __future__ import annotations

import uuid
from decimal import Decimal
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models.cart import Cart
from app.models.product import Product, Stock

TEST_DB_URL = settings.TEST_DATABASE_URL


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create the test database schema once per session."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session that is rolled back after each test."""
    TestSession = async_sessionmaker(test_engine, expire_on_commit=False)
    async with TestSession() as session:
        async with session.begin():
            yield session
            await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client that uses the test DB session via dependency override."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helper fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def create_product(db_session: AsyncSession):
    """Factory fixture: create_product(stock=10, **kwargs) -> Product."""

    async def _factory(
        stock: int = 10,
        erp_id: str | None = None,
        name: str = "Test Product",
        description: str = "A test product",
        price: Decimal = Decimal("29.90"),
        image_url: str | None = None,
        model_compat: str | None = "Test Model",
    ) -> Product:
        unique_erp_id = erp_id or f"TEST-{uuid.uuid4().hex[:8].upper()}"
        product = Product(
            erp_id=unique_erp_id,
            name=name,
            description=description,
            price=price,
            image_url=image_url,
            model_compat=model_compat,
        )
        db_session.add(product)
        await db_session.flush()

        stock_row = Stock(
            product_id=product.id,
            quantity_available=stock,
            quantity_reserved=0,
        )
        db_session.add(stock_row)
        await db_session.flush()

        return product

    return _factory


@pytest_asyncio.fixture
async def create_cart(db_session: AsyncSession):
    """Factory fixture: create_cart() -> Cart."""

    async def _factory(session_id: str | None = None) -> Cart:
        sid = session_id or str(uuid.uuid4())
        cart = Cart(session_id=sid)
        db_session.add(cart)
        await db_session.flush()
        return cart

    return _factory
