from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order


@pytest.mark.asyncio
async def test_checkout_success(create_product, create_cart, client: AsyncClient, db_session: AsyncSession):
    """Full checkout flow: create product, cart, add item, checkout → HTTP 201, order confirmed."""
    product = await create_product(stock=5, price=Decimal("49.90"))
    session_id = str(uuid.uuid4())

    # Create cart
    cart_resp = await client.post("/api/cart", json={"session_id": session_id})
    assert cart_resp.status_code == 201

    # Add item
    add_resp = await client.post(
        f"/api/cart/{session_id}/items",
        json={"product_id": str(product.id), "quantity": 2},
    )
    assert add_resp.status_code == 201

    # Checkout
    checkout_resp = await client.post(
        "/api/orders/checkout",
        json={
            "idempotency_key": str(uuid.uuid4()),
            "session_id": session_id,
            "customer_name": "João Silva",
            "customer_email": "joao@example.com",
            "customer_address": "Rua das Flores, 123, São Paulo, SP",
        },
    )
    assert checkout_resp.status_code == 201
    data = checkout_resp.json()
    assert data["status"] == "confirmed"
    assert data["customer_name"] == "João Silva"
    assert len(data["items"]) == 1
    assert data["items"][0]["quantity"] == 2
    assert Decimal(data["total_amount"]) == Decimal("99.80")


@pytest.mark.asyncio
async def test_checkout_idempotency(create_product, client: AsyncClient, db_session: AsyncSession):
    """Same idempotency_key twice: second call returns HTTP 200 with same order_id, no duplicate."""
    product = await create_product(stock=5)
    session_id = str(uuid.uuid4())
    idempotency_key = str(uuid.uuid4())

    await client.post("/api/cart", json={"session_id": session_id})
    await client.post(
        f"/api/cart/{session_id}/items",
        json={"product_id": str(product.id), "quantity": 1},
    )

    checkout_payload = {
        "idempotency_key": idempotency_key,
        "session_id": session_id,
        "customer_name": "Maria Santos",
        "customer_email": "maria@example.com",
        "customer_address": "Av. Paulista, 1000, São Paulo, SP",
    }

    # First call → 201
    resp1 = await client.post("/api/orders/checkout", json=checkout_payload)
    assert resp1.status_code == 201
    order_id_1 = resp1.json()["order_id"]

    # Second call with same key → 200, same order_id
    resp2 = await client.post("/api/orders/checkout", json=checkout_payload)
    assert resp2.status_code == 200
    order_id_2 = resp2.json()["order_id"]

    assert order_id_1 == order_id_2

    # Confirm only one order in the DB with this key
    result = await db_session.execute(
        select(Order).where(Order.idempotency_key == idempotency_key)
    )
    orders = result.scalars().all()
    assert len(orders) == 1


@pytest.mark.asyncio
async def test_checkout_empty_cart(client: AsyncClient):
    """Checking out with an empty cart returns HTTP 400."""
    session_id = str(uuid.uuid4())

    await client.post("/api/cart", json={"session_id": session_id})

    resp = await client.post(
        "/api/orders/checkout",
        json={
            "idempotency_key": str(uuid.uuid4()),
            "session_id": session_id,
            "customer_name": "Test User",
            "customer_email": "test@example.com",
            "customer_address": "Rua Test, 1, Cidade, Estado",
        },
    )
    assert resp.status_code == 400
    assert "vazio" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_checkout_missing_cart(client: AsyncClient):
    """Checking out with an unknown session_id returns HTTP 404."""
    resp = await client.post(
        "/api/orders/checkout",
        json={
            "idempotency_key": str(uuid.uuid4()),
            "session_id": str(uuid.uuid4()),  # non-existent session
            "customer_name": "Ghost User",
            "customer_email": "ghost@example.com",
            "customer_address": "Endereço Fantasma, 0, Cidade, Estado",
        },
    )
    assert resp.status_code == 404
    assert "carrinho" in resp.json()["detail"].lower()
