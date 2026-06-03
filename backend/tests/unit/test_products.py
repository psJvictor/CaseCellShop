from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_list_products(create_product, client: AsyncClient, db_session: AsyncSession):
    """Inserting 3 products and listing returns all 3."""
    await create_product(name="Product A", erp_id="LST-001")
    await create_product(name="Product B", erp_id="LST-002")
    await create_product(name="Product C", erp_id="LST-003")

    resp = await client.get("/api/products")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 3
    assert len(data["items"]) >= 3


@pytest.mark.asyncio
async def test_list_products_pagination(create_product, client: AsyncClient, db_session: AsyncSession):
    """5 products with page_size=2, page=2 returns 2 items."""
    for i in range(5):
        await create_product(name=f"Paged Product {i}", erp_id=f"PAG-{i:03d}")

    resp = await client.get("/api/products?page=2&page_size=2")
    assert resp.status_code == 200
    data = resp.json()
    assert data["page"] == 2
    assert data["page_size"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_get_product(create_product, client: AsyncClient, db_session: AsyncSession):
    """GET /api/products/{id} returns correct product data."""
    product = await create_product(
        name="Capinha Especial",
        erp_id="GET-001",
        price=Decimal("55.00"),
        stock=7,
    )

    resp = await client.get(f"/api/products/{product.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(product.id)
    assert data["name"] == "Capinha Especial"
    assert Decimal(data["price"]) == Decimal("55.00")
    assert data["stock_available"] == 7


@pytest.mark.asyncio
async def test_get_product_not_found(client: AsyncClient):
    """GET with a non-existent UUID returns HTTP 404."""
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/products/{fake_id}")
    assert resp.status_code == 404
