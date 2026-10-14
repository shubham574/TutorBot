"""ARQ worker configuration and lifecycle."""
from typing import Any, Dict
from arq.connections import RedisSettings
from app.config.settings import settings
from app.config.logging_config import setup_logging, logger
from app.workers.tasks import process_whatsapp_message


async def startup(ctx: Dict[Any, Any]) -> None:
    """Worker startup hook."""
    setup_logging(log_level=settings.LOG_LEVEL)
    logger.info("ARQ Worker starting up", redis_url=settings.REDIS_URL)


async def shutdown(ctx: Dict[Any, Any]) -> None:
    """Worker shutdown hook."""
    logger.info("ARQ Worker shutting down")


class WorkerSettings:
    """ARQ Worker configuration class."""
    functions = [process_whatsapp_message]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 20
    job_timeout = 60
