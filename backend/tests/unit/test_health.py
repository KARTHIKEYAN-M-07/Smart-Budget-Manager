"""Unit tests for Health Check and Core Middleware"""

from unittest.mock import patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_endpoint(async_client: AsyncClient):
    """Test root endpoint returns 200 with service information."""
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "Smart Family Budget Manager" in data["app"]
    assert "version" in data


@pytest.mark.asyncio
async def test_health_check_healthy(async_client: AsyncClient):
    """Test health check when database is healthy."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert "timestamp" in data
    assert data["version"] == "0.1.0"


@pytest.mark.asyncio
async def test_health_check_unhealthy(async_client: AsyncClient):
    """Test health check returns 503 when database is disconnected without leaking secrets."""
    with patch("app.api.v1.health.check_database_health", return_value=False):
        response = await async_client.get("/api/v1/health")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["database"] == "disconnected"
        # Confirm no database connection strings or credentials leaked in response
        response_text = response.text.lower()
        assert "password" not in response_text
        assert "postgres" not in response_text
        assert "sqlite" not in response_text


@pytest.mark.asyncio
async def test_security_headers_present(async_client: AsyncClient):
    """Test defensive security headers are injected into HTTP responses."""
    response = await async_client.get("/api/v1/health")
    headers = response.headers
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert "1; mode=block" in headers.get("X-XSS-Protection", "")
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


@pytest.mark.asyncio
async def test_cors_headers(async_client: AsyncClient):
    """Test CORS preflight handling for allowed origin."""
    response = await async_client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
