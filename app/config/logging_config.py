"""Structured logging configuration with PII redaction."""
import logging
import re
import sys
from typing import Any, MutableMapping
import structlog

# Regex to match phone numbers (E.164 or typical 10-15 digits)
PHONE_REGEX = re.compile(r"(\+?\d{1,4})?(\d{2,4})(\d{4})(\d{2,4})")


def mask_phone_number(val: str) -> str:
    """Masks phone number leaving only prefix and last 4 digits (e.g. +91*****1234)."""
    if len(val) < 8:
        return "****"
    return f"{val[:3]}*****{val[-4:]}"


def pii_redactor(
    logger: Any, method_name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Processor to redact PII like phone numbers from log event dictionaries."""
    for key, value in list(event_dict.items()):
        if isinstance(value, str):
            if "phone" in key.lower() or "recipient" in key.lower() or "sender" in key.lower():
                event_dict[key] = mask_phone_number(value)
        elif isinstance(value, dict):
            # Shallow nested dict check
            for sub_k, sub_v in list(value.items()):
                if isinstance(sub_v, str) and ("phone" in sub_k.lower() or "from" in sub_k.lower()):
                    value[sub_k] = mask_phone_number(sub_v)
    return event_dict


def setup_logging(log_level: str = "INFO", json_logs: bool = True) -> None:
    """Configures standard logging and structlog."""
    level = getattr(logging, log_level.upper(), logging.INFO)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        pii_redactor,
    ]

    if json_logs:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(level)

    # Suppress verbose noisy loggers
    for noisy in ["uvicorn.access", "httpx", "httpcore"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)


logger = structlog.get_logger("tutorbot")
