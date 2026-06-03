from __future__ import annotations

import logging
import time
import uuid

import structlog
import structlog.contextvars
import structlog.dev
import structlog.stdlib
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.config import settings

log = structlog.get_logger()

# Map level names to stdlib integer levels
_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def configure_logging() -> None:
    """Configure structlog.

    LOG_FORMAT=console  →  coloured, human-readable output (default)
    LOG_FORMAT=json     →  single-line JSON per event (for production / log aggregators)
    """
    level = _LEVEL_MAP.get(settings.LOG_LEVEL.upper(), logging.INFO)
    use_json = settings.LOG_FORMAT.lower() == "json"

    # Processors shared by both renderers
    shared = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(
            fmt="iso" if use_json else "%H:%M:%S"
        ),
        structlog.processors.StackInfoRenderer(),
    ]

    if use_json:
        processors = shared + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        processors = shared + [
            structlog.dev.ConsoleRenderer(
                colors=True,
                exception_formatter=structlog.dev.plain_traceback,
                sort_keys=False,
            ),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,  # allow reconfiguration in tests
    )


class LoggingMiddleware(BaseHTTPMiddleware):
    """Log every HTTP request with method, path, status code and duration."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: any) -> Response:
        request_id = str(uuid.uuid4())[:8]          # short 8-char prefix — enough for correlation
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(req_id=request_id)

        log.info(
            "→ request",
            method=request.method,
            path=request.url.path,
        )

        start = time.perf_counter()
        try:
            response = await call_next(request)
            ms = round((time.perf_counter() - start) * 1000, 1)

            # choose log level based on status code
            status = response.status_code
            if status < 400:
                log.info("← response", status=status, ms=ms)
            elif status < 500:
                log.warning("← response", status=status, ms=ms)
            else:
                log.error("← response", status=status, ms=ms)

            return response
        except Exception:
            ms = round((time.perf_counter() - start) * 1000, 1)
            log.exception("← response error", ms=ms)
            raise
        finally:
            structlog.contextvars.clear_contextvars()
