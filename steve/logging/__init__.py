"""STEVE High-Performance Structured Logging & Observability Subsystem."""

from __future__ import annotations

import logging
import sys
from typing import Any

from steve.logging.async_handler import AsyncLogQueueHandler
from steve.logging.formatter import StructuredLogFormatter
from steve.logging.logger import SetveLogger, SteveLogger

__all__ = [
    "AsyncLogQueueHandler",
    "SetveLogger",
    "SteveLogger",
    "StructuredLogFormatter",
    "configure_logging",
    "get_logger",
]


def get_logger(name: str = "steve", **context: Any) -> SteveLogger:
    """Factory helper to obtain a contextual SteveLogger instance."""
    return SteveLogger(name, context=context)


def configure_logging(
    level: int = logging.INFO,
    json_mode: bool = False,
    stream: Any = sys.stdout,
) -> logging.Handler:
    """Configure root STEVE logging handler with StructuredLogFormatter."""
    root_logger = logging.getLogger("steve")
    root_logger.setLevel(level)

    # Remove existing handlers to avoid duplicate log entries
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)

    handler = logging.StreamHandler(stream)
    handler.setLevel(level)
    handler.setFormatter(StructuredLogFormatter(json_mode=json_mode))
    root_logger.addHandler(handler)
    return handler
