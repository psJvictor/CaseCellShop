from __future__ import annotations

import asyncio
import random
import time
from decimal import Decimal

import structlog

from app.config import settings

log = structlog.get_logger()

MOCK_PRODUCTS: list[dict] = [
    {
        "erp_id": "ERP-001",
        "name": "Capinha iPhone 15 Pro - Preta Fosca",
        "description": "Proteção premium para iPhone 15 Pro",
        "price": Decimal("49.90"),
        "image_url": "https://placehold.co/400x400/1a1a1a/white?text=iPhone+15+Pro",
        "model_compat": "iPhone 15 Pro",
        "stock": 15,
    },
    {
        "erp_id": "ERP-002",
        "name": "Capinha iPhone 14 - Transparente",
        "description": "Case cristal ultra-fina para iPhone 14",
        "price": Decimal("34.90"),
        "image_url": "https://placehold.co/400x400/e8f4f8/333?text=iPhone+14",
        "model_compat": "iPhone 14",
        "stock": 8,
    },
    {
        "erp_id": "ERP-003",
        "name": "Capinha Samsung S24 Ultra - Azul",
        "description": "Case premium para S24 Ultra",
        "price": Decimal("59.90"),
        "image_url": "https://placehold.co/400x400/1565c0/white?text=S24+Ultra",
        "model_compat": "Samsung Galaxy S24 Ultra",
        "stock": 5,
    },
    {
        "erp_id": "ERP-004",
        "name": "Capinha Samsung S23 - Silicone Rosa",
        "description": "Silicone macio anti-impacto para S23",
        "price": Decimal("39.90"),
        "image_url": "https://placehold.co/400x400/f8bbd9/333?text=S23",
        "model_compat": "Samsung Galaxy S23",
        "stock": 20,
    },
    {
        "erp_id": "ERP-005",
        "name": "Capinha Motorola G84 - Verde Militar",
        "description": "Case resistente para Moto G84",
        "price": Decimal("29.90"),
        "image_url": "https://placehold.co/400x400/2d5016/white?text=Moto+G84",
        "model_compat": "Motorola Moto G84",
        "stock": 12,
    },
    {
        "erp_id": "ERP-006",
        "name": "Capinha iPhone 15 - MagSafe Compatível",
        "description": "Case com suporte MagSafe para iPhone 15",
        "price": Decimal("79.90"),
        "image_url": "https://placehold.co/400x400/ff6b35/white?text=MagSafe",
        "model_compat": "iPhone 15",
        "stock": 3,
    },
    {
        "erp_id": "ERP-007",
        "name": "Capinha Xiaomi Redmi Note 13 - Reforçada",
        "description": "Proteção militar para Redmi Note 13",
        "price": Decimal("44.90"),
        "image_url": "https://placehold.co/400x400/ff8f00/white?text=Redmi",
        "model_compat": "Xiaomi Redmi Note 13",
        "stock": 18,
    },
    {
        "erp_id": "ERP-008",
        "name": 'Capinha Universal Carteira - Couro Marrom',
        "description": "Carteira com compartimento para cartões",
        "price": Decimal("54.90"),
        "image_url": "https://placehold.co/400x400/795548/white?text=Wallet",
        "model_compat": 'Universal 6.5"',
        "stock": 7,
    },
    {
        "erp_id": "ERP-009",
        "name": "Capinha iPhone 13 Mini - Líquido Glitter",
        "description": "Case com glitter líquido colorido",
        "price": Decimal("37.90"),
        "image_url": "https://placehold.co/400x400/9c27b0/white?text=Glitter",
        "model_compat": "iPhone 13 Mini",
        "stock": 25,
    },
    {
        "erp_id": "ERP-010",
        "name": "Capinha Samsung A54 - Anti-Shock Preta",
        "description": "Proteção máxima anti-choque para A54",
        "price": Decimal("32.90"),
        "image_url": "https://placehold.co/400x400/212121/white?text=A54",
        "model_compat": "Samsung Galaxy A54",
        "stock": 1,
    },
]


class CircuitOpenError(Exception):
    pass


class ERPServiceBase:
    async def get_products(self) -> list[dict]:
        raise NotImplementedError


class MockERPService(ERPServiceBase):
    def __init__(self) -> None:
        self._failure_count: int = 0
        self._circuit_state: str = "closed"  # closed, open, half-open
        self._last_failure_at: float | None = None
        self._cache: list[dict] = []

    async def get_products(self) -> list[dict]:
        # Circuit breaker check
        if self._circuit_state == "open":
            elapsed = time.monotonic() - (self._last_failure_at or 0)
            if elapsed < settings.ERP_CIRCUIT_RECOVERY_SECONDS:
                log.warning(
                    "erp_circuit_open_serving_cache",
                    failure_count=self._failure_count,
                )
                if self._cache:
                    return self._cache
                raise CircuitOpenError("ERP circuit is open and no cache available")
            else:
                self._circuit_state = "half-open"
                log.info("erp_circuit_half_open")

        # Simulate delay
        if settings.MOCK_ERP_DELAY_SECONDS > 0:
            await asyncio.sleep(settings.MOCK_ERP_DELAY_SECONDS)

        # Simulate failures
        if random.random() < settings.MOCK_ERP_FAIL_RATE:
            self._failure_count += 1
            self._last_failure_at = time.monotonic()
            if self._failure_count >= settings.ERP_CIRCUIT_FAILURE_THRESHOLD:
                self._circuit_state = "open"
                log.error("erp_circuit_opened", failure_count=self._failure_count)
            raise ConnectionError(
                f"Mock ERP simulated failure ({self._failure_count})"
            )

        # Success path
        self._failure_count = 0
        if self._circuit_state == "half-open":
            self._circuit_state = "closed"
            log.info("erp_circuit_closed")
        self._cache = MOCK_PRODUCTS.copy()
        return self._cache


_erp_service_instance: ERPServiceBase | None = None


def get_erp_service() -> ERPServiceBase:
    global _erp_service_instance
    if _erp_service_instance is None:
        _erp_service_instance = MockERPService()
    return _erp_service_instance
