"""ARQ worker configuration and lifecycle."""
from typing import Any, Dict
from arq.connections import RedisSettings
from arq.cron import cron
from app.config.settings import settings
from app.config.logging_config import setup_logging, logger
from app.workers.tasks import process_whatsapp_message, dispatch_scheduled_nudges, run_data_retention_job


async def startup(ctx: Dict[Any, Any]) -> None:
    """Worker startup hook."""
    setup_logging(log_level=settings.LOG_LEVEL)
    logger.info("ARQ Worker starting up", redis_url=settings.REDIS_URL)


async def shutdown(ctx: Dict[Any, Any]) -> None:
    """Worker shutdown hook."""
    logger.info("ARQ Worker shutting down")


class WorkerSettings:
    """ARQ Worker configuration class."""
    functions = [process_whatsapp_message, dispatch_scheduled_nudges, run_data_retention_job]
    cron_jobs = [
        cron(dispatch_scheduled_nudges, minute={0, 30}),
        cron(run_data_retention_job, hour=3, minute=0),  # Run daily at 3 AM
    ]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 20
    job_timeout = 60