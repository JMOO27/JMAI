"""Application-wide logging helpers.

Use this module from any application module instead of configuring logging in
multiple places::

    from app.app_logging import get_logger

    logger = get_logger(__name__)
    logger.info("Application started")

Call :func:`configure_logging` once during application startup when a custom
level is needed. ``APP_LOG_LEVEL`` can also be used to override the default
level without changing code.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Final


DEFAULT_LOG_LEVEL: Final[int] = logging.INFO
LOG_FORMAT: Final[str] = (
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)
DEFAULT_LOG_FILE: Final[str] = "app.log"


def _log_level(level: int | str | None) -> int:
    """Return a valid logging level from an integer, name, or environment."""
    value = level if level is not None else os.getenv("APP_LOG_LEVEL", "INFO")

    if isinstance(value, int):
        return value

    resolved_level = getattr(logging, value.upper(), None)
    if isinstance(resolved_level, int):
        return resolved_level

    return DEFAULT_LOG_LEVEL


def configure_logging(
    level: int | str | None = None,
    log_file: str | os.PathLike[str] | None = None,
) -> None:
    """Configure shared console and append-mode file handlers.

    The function is safe to call repeatedly: it updates the existing handler
    instead of adding duplicates. ``APP_LOG_FILE`` can be used to change the
    file location; it defaults to ``app.log`` in the current working directory.
    Logs from child loggers such as ``app.services.chat_service`` propagate to
    the shared ``app`` logger.
    """
    app_logger = logging.getLogger("app")
    app_logger.setLevel(_log_level(level))
    app_logger.propagate = False
    log_path = Path(log_file or os.getenv("APP_LOG_FILE", DEFAULT_LOG_FILE))
    log_path.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(LOG_FORMAT)
    console_handler = next(
        (
            existing
            for existing in app_logger.handlers
            if getattr(existing, "_jmai_console_handler", False)
        ),
        None,
    )

    if console_handler is None:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler._jmai_console_handler = True  # type: ignore[attr-defined]
        app_logger.addHandler(console_handler)

    console_handler.setLevel(app_logger.level)
    console_handler.setFormatter(formatter)

    file_handler = next(
        (
            existing
            for existing in app_logger.handlers
            if getattr(existing, "_jmai_file_handler", False)
        ),
        None,
    )

    if file_handler is None or Path(file_handler.baseFilename) != log_path.resolve():
        if file_handler is not None:
            app_logger.removeHandler(file_handler)
            file_handler.close()
        file_handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
        file_handler._jmai_file_handler = True  # type: ignore[attr-defined]
        app_logger.addHandler(file_handler)

    file_handler.setLevel(app_logger.level)
    file_handler.setFormatter(formatter)


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a configured logger for an application module.

    ``name`` should normally be ``__name__`` so log records identify their
    source module. Calling this helper is enough to make the logger usable.
    """
    app_logger = logging.getLogger("app")
    if not any(
        getattr(handler, "_jmai_console_handler", False)
        for handler in app_logger.handlers
    ):
        configure_logging()
    return logging.getLogger(name or "app")


def log(
    message: str,
    level: int = logging.INFO,
    *,
    name: str | None = None,
    exc_info: bool = False,
) -> None:
    """Append a message to the configured log file and console.

    Example: ``log("Chat request completed")``.
    """
    get_logger(name).log(level, message, exc_info=exc_info)


# Convenient default for small scripts: ``from app.app_logging import logger``.
logger = get_logger()


__all__ = ["configure_logging", "get_logger", "log", "logger"]

