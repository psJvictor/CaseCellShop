from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from app.services.erp_service import CircuitOpenError, MockERPService


@pytest.mark.asyncio
async def test_mock_erp_returns_products():
    """get_products() returns the 10 mock products."""
    svc = MockERPService()
    products = await svc.get_products()
    assert len(products) == 10
    # Verify structure of first product
    p = products[0]
    assert "erp_id" in p
    assert "name" in p
    assert "price" in p
    assert "stock" in p


@pytest.mark.asyncio
async def test_circuit_opens_after_threshold():
    """Circuit opens after ERP_CIRCUIT_FAILURE_THRESHOLD consecutive failures."""
    svc = MockERPService()

    # Override settings inline
    with patch("app.services.erp_service.settings") as mock_settings:
        mock_settings.MOCK_ERP_DELAY_SECONDS = 0
        mock_settings.MOCK_ERP_FAIL_RATE = 1.0  # Always fail
        mock_settings.ERP_CIRCUIT_FAILURE_THRESHOLD = 3
        mock_settings.ERP_CIRCUIT_RECOVERY_SECONDS = 30

        for _ in range(3):
            with pytest.raises(ConnectionError):
                await svc.get_products()

        assert svc._circuit_state == "open"
        assert svc._failure_count >= 3


@pytest.mark.asyncio
async def test_circuit_serves_cache_when_open():
    """When circuit is open but cache exists, cache is returned instead of raising."""
    svc = MockERPService()

    # Populate the cache first with a successful call
    with patch("app.services.erp_service.settings") as mock_settings:
        mock_settings.MOCK_ERP_DELAY_SECONDS = 0
        mock_settings.MOCK_ERP_FAIL_RATE = 0.0
        mock_settings.ERP_CIRCUIT_FAILURE_THRESHOLD = 3
        mock_settings.ERP_CIRCUIT_RECOVERY_SECONDS = 9999

        products_before = await svc.get_products()
        assert len(products_before) == 10

    # Now force the circuit open
    svc._circuit_state = "open"
    svc._last_failure_at = time.monotonic()

    with patch("app.services.erp_service.settings") as mock_settings:
        mock_settings.MOCK_ERP_DELAY_SECONDS = 0
        mock_settings.MOCK_ERP_FAIL_RATE = 0.0
        mock_settings.ERP_CIRCUIT_FAILURE_THRESHOLD = 3
        mock_settings.ERP_CIRCUIT_RECOVERY_SECONDS = 9999

        # Should return from cache without raising
        cached = await svc.get_products()
        assert len(cached) == 10


@pytest.mark.asyncio
async def test_circuit_recovery():
    """After recovery period, half-open state allows a call; on success circuit closes."""
    svc = MockERPService()
    # Force circuit open with stale failure time (past recovery window)
    svc._circuit_state = "open"
    svc._failure_count = 5
    svc._last_failure_at = time.monotonic() - 100  # well past recovery

    with patch("app.services.erp_service.settings") as mock_settings:
        mock_settings.MOCK_ERP_DELAY_SECONDS = 0
        mock_settings.MOCK_ERP_FAIL_RATE = 0.0  # Next call succeeds
        mock_settings.ERP_CIRCUIT_FAILURE_THRESHOLD = 3
        mock_settings.ERP_CIRCUIT_RECOVERY_SECONDS = 30

        # Should transition to half-open and then closed on success
        products = await svc.get_products()
        assert len(products) == 10

    assert svc._circuit_state == "closed"
    assert svc._failure_count == 0
