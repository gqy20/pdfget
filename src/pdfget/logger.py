#!/usr/bin/env python3
"""Project-wide structured logging configuration."""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from pathlib import Path
from types import TracebackType
from typing import Any, ParamSpec, TypeVar, cast

import structlog

from .config import LOG_LEVEL

P = ParamSpec("P")
R = TypeVar("R")

Logger = structlog.stdlib.BoundLogger

_CONFIGURED = False
_LOG_FORMAT = "text"
_LOG_LEVEL = LOG_LEVEL


class EventRenamer:
    """Rename structlog's event key to message for JSON log readability."""

    def __call__(
        self, logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
    ) -> dict[str, Any]:
        if "event" in event_dict:
            event_dict["message"] = event_dict.pop("event")
        return event_dict


def _level_name(level: str | int | None) -> str:
    if isinstance(level, int):
        return logging.getLevelName(level)
    return (level or LOG_LEVEL).upper()


def configure_logging(
    *,
    level: str | int | None = None,
    log_format: str = "text",
    quiet: bool = False,
    log_file: Path | None = None,
    force: bool = False,
) -> None:
    """Configure logging for all pdfget modules.

    Logs are always emitted to stderr so stdout can remain machine-readable.
    """
    global _CONFIGURED, _LOG_FORMAT, _LOG_LEVEL

    if _CONFIGURED and not force:
        return

    if force:
        structlog.reset_defaults()

    level_name = "ERROR" if quiet else _level_name(level)
    log_level = getattr(logging, level_name, logging.INFO)
    _LOG_FORMAT = log_format
    _LOG_LEVEL = level_name

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=False)
    shared_processors: list[Any] = [
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if log_format == "json":
        renderer: Any = structlog.processors.JSONRenderer(ensure_ascii=False)
        formatter_processors = [
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            EventRenamer(),
            renderer,
        ]
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())
        formatter_processors = [
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ]

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=formatter_processors,
    )

    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setLevel(log_level)
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    root_logger.setLevel(log_level)

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    _CONFIGURED = True


def setup_logger(
    name: str,
    level: str | None = None,
    log_format: str | None = None,
    use_colors: bool = True,
    log_file: Path | None = None,
) -> Logger:
    """Return a configured structured logger.

    The ``use_colors`` parameter is kept for backward compatibility; text output
    auto-detects terminal color support.
    """
    del use_colors
    configure_logging(
        level=level,
        log_format=log_format or _LOG_FORMAT,
        log_file=log_file,
    )
    return cast(Logger, structlog.get_logger(name))


def get_logger(name: str) -> Logger:
    """Get a module logger."""
    return setup_logger(name)


def get_main_logger() -> Logger:
    """Get the main CLI logger."""
    return get_logger("PDFDownloader")


def get_fetcher_logger() -> Logger:
    """Get the paper fetcher logger."""
    return get_logger("PaperFetcher")


def get_manager_logger() -> Logger:
    """Get the download manager logger."""
    return get_logger("DownloadManager")


def get_counter_logger() -> Logger:
    """Get the PMCID counter logger."""
    return get_logger("PMCIDCounter")


def log_function_call(logger: Logger | None = None) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator that logs function entry, success, and failure."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        import functools

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            active_logger = logger or get_logger(func.__module__)
            active_logger.debug("function_call", function=func.__name__)
            try:
                result = func(*args, **kwargs)
                active_logger.debug("function_success", function=func.__name__)
                return result
            except Exception:
                active_logger.error(
                    "function_failed", function=func.__name__, exc_info=True
                )
                raise

        return wrapper

    return decorator


class LogContext:
    """Temporarily change the root log level."""

    def __init__(self, logger: Logger, level: str):
        self.logger = logger
        self.new_level = getattr(logging, level.upper())
        self.old_level: int | None = None

    def __enter__(self) -> LogContext:
        wrapped = logging.getLogger(self.logger.name)
        self.old_level = wrapped.level
        wrapped.setLevel(self.new_level)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self.old_level is not None:
            logging.getLogger(self.logger.name).setLevel(self.old_level)
