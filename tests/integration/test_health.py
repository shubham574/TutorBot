"""Integration tests for health endpoints."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_liveness(app_client: AsyncClient):
    response = await app_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "tutorbot"


@pytest.mark.asyncio
async def test_root_endpoint(app_client: AsyncClient):
    response = await app_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "TutorBot"
    assert data["status"] == "online"
