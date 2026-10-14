"""FastAPI Application entrypoint and lifecycle."""
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.deps import get_redis_client
from app.api.v1 import api_v1_router
from app.config.settings import settings
from app.config.logging_config import setup_logging, logger


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages application startup and shutdown resources."""
    setup_logging(log_level=settings.LOG_LEVEL)
    logger.info("Starting TutorBot application", environment=settings.ENVIRONMENT, dry_run=settings.DRY_RUN)

    # Initialize Redis connection for fast deduplication
    redis = get_redis_client()
    app.state.redis = redis

    # Initialize ARQ Pool for queueing jobs
    try:
        arq_pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        app.state.arq_pool = arq_pool
        logger.info("ARQ Redis pool successfully initialized")
    except Exception as e:
        logger.warning("Could not connect to Redis ARQ pool (local tests may mock this)", error=str(e))
        app.state.arq_pool = None

    yield

    # Teardown
    if app.state.arq_pool:
        await app.state.arq_pool.close()
    if app.state.redis:
        await app.state.redis.aclose()
    logger.info("TutorBot application shutdown complete")


def create_app() -> FastAPI:
    """Creates and configures the FastAPI application instance."""
    app = FastAPI(
        title="TutorBot API",
        description="Agentic personal-tutor WhatsApp bot backend",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_v1_router, prefix="/api/v1")

    @app.get("/")
    async def root():
        return {
            "name": "TutorBot",
            "version": "0.1.0",
            "status": "online",
            "docs": "/docs",
        }

    return app


app = create_app()
