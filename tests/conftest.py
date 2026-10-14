"""Pytest global fixtures and test environment configuration."""
import asyncio
import os
import pytest
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.config.settings import settings
from app.models.base import Base
from app.main import create_app

# Force DRY_RUN mode for testing
settings.DRY_RUN = True
settings.WHATSAPP_APP_SECRET = "test_secret_for_unit_tests"
settings.WHATSAPP_VERIFY_TOKEN = "test_verify_token_123"


class MockRedis:
    """In-memory mock for async Redis operations."""
    def __init__(self):
        self._store = {}

    async def set(self, name: str, value: str, ex: int = None, nx: bool = False) -> bool:
        if nx and name in self._store:
            return False
        self._store[name] = value
        return True

    async def get(self, name: str):
        return self._store.get(name)

    async def ping(self):
        return True

    async def aclose(self):
        pass


class MockArqPool:
    """Mock for ARQ Redis connection pool."""
    def __init__(self):
        self.enqueued_jobs = []

    async def enqueue_job(self, function_name: str, *args, **kwargs):
        job = {"function": function_name, "args": args, "kwargs": kwargs}
        self.enqueued_jobs.append(job)
        return job

    async def close(self):
        pass


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_redis():
    """Provides an isolated MockRedis instance."""
    return MockRedis()


@pytest.fixture
def mock_arq_pool():
    """Provides a MockArqPool instance."""
    return MockArqPool()


@pytest.fixture
async def app_client(mock_redis, mock_arq_pool) -> AsyncGenerator[AsyncClient, None]:
    """Provides an async HTTP client configured with mocked Redis and ARQ state."""
    app = create_app()
    app.state.redis = mock_redis
    app.state.arq_pool = mock_arq_pool

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client
