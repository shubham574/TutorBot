"""Health check endpoints."""
from fastapi import APIRouter, Response, status
from sqlalchemy import text
from app.api.deps import async_session_factory, get_redis_client
from app.config.logging_config import logger

router = APIRouter()


@router.get("/health", status_code=status.HTTP_200_OK)
async def liveness() -> dict:
    """Basic liveness probe."""
    return {"status": "ok", "service": "tutorbot"}


@router.get("/health/ready")
async def readiness(response: Response) -> dict:
    """Readiness probe checking PostgreSQL and Redis connectivity."""
    db_ok = False
    redis_ok = False

    # Check Database
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
            db_ok = True
    except Exception as e:
        logger.error("Readiness check failed: Database unreachable", error=str(e))

    # Check Redis
    try:
        redis = get_redis_client()
        await redis.ping()
        await redis.aclose()
        redis_ok = True
    except Exception as e:
        logger.error("Readiness check failed: Redis unreachable", error=str(e))

    is_ready = db_ok and redis_ok
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ready" if is_ready else "degraded",
        "database": "connected" if db_ok else "unavailable",
        "redis": "connected" if redis_ok else "unavailable",
    }
