from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Stock


@pytest.mark.asyncio
async def test_create_cart(client: AsyncClient):
    """POST /api/cart returns 201 with a session_id."""
    resp = await client.post("/api/cart", json={})
    assert resp.status_code == 201
    data = resp.json()
    assert "cart_id" in data
    assert "session_id" in data
    assert len(data["session_id"]) > 0


@pytest.mark.asyncio
async def test_add_item_to_cart(create_product, client: AsyncClient, db_session: AsyncSession):
    """Adding an item reserves stock and returns 201."""
    product = await create_product(stock=10)
    session_id = str(uuid.uuid4())

    await client.post("/api/cart", json={"session_id": session_id})

    resp = await client.post(
        f"/api/cart/{session_id}/items",
        json={"product_id": str(product.id), "quantity": 3},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["quantity"] == 3
    assert "reservation_id" in data

    # Verify stock was reserved
    stock = (
        await db_session.execute(select(Stock).where(Stock.product_id == product.id))
    ).scalar_one()
    assert stock.quantity_available == 7
    assert stock.quantity_reserved == 3


@pytest.mark.asyncio
async def test_add_item_insufficient_stock(create_product, client: AsyncClient):
    """Trying to add more items than available stock returns 409."""
    product = await create_product(stock=2)
    session_id = str(uuid.uuid4())

    await client.post("/api/cart", json={"session_id": session_id})

    resp = await client.post(
        f"/api/cart/{session_id}/items",
        json={"product_id": str(product.id), "quantity": 5},
    )
    assert resp.status_code == 409
    assert "insuficiente" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_cart_detail(create_product, client: AsyncClient, db_session: AsyncSession):
    """GET /api/cart/{session_id} returns correct cart structure."""
    product = await create_product(stock=10, price=Decimal("39.90"), name="Capinha Test")
    session_id = str(uuid.uuid4())

    await client.post("/api/cart", json={"session_id": session_id})
    await client.post(
        f"/api/cart/{session_id}/items",
        json={"product_id": str(product.id), "quantity": 2},
    )

    resp = await client.get(f"/api/cart/{session_id}")
    assert resp.status_code == 200
    data = resp.json()

    assert data["session_id"] == session_id
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["product_id"] == str(product.id)
    assert item["product_name"] == "Capinha Test"
    assert item["quantity"] == 2
    assert Decimal(item["unit_price"]) == Decimal("39.90")
    assert item["reservation_id"] is not None
    assert item["expires_at"] is not None
    assert Decimal(data["total_amount"]) == Decimal("79.80")


@pytest.mark.asyncio
async def test_remove_item_from_cart(create_product, client: AsyncClient, db_session: AsyncSession):
    """Adding then removing an item releases stock back to available."""
    product = await create_product(stock=10)
    session_id = str(uuid.uuid4())

    await client.post("/api/cart", json={"session_id": session_id})
    await client.post(
        f"/api/cart/{session_id}/items",
        json={"product_id": str(product.id), "quantity": 4},
    )

    # Verify stock was reserved
    stock = (
        await db_session.execute(select(Stock).where(Stock.product_id == product.id))
    ).scalar_one()
    assert stock.quantity_available == 6

    # Remove item
    resp = await client.delete(f"/api/cart/{session_id}/items/{product.id}")
    assert resp.status_code == 204

    # Stock should be back to 10
    await db_session.refresh(stock)
    assert stock.quantity_available == 10
    assert stock.quantity_reserved == 0

    # Cart should be empty
    cart_resp = await client.get(f"/api/cart/{session_id}")
    assert cart_resp.status_code == 200
    assert cart_resp.json()["items"] == []
