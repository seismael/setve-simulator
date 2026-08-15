"""High-Performance Structured JSON and Console Log Formatters."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any


class StructuredLogFormatter(logging.Formatter):
    """Structured log formatter with JSON output for aggregators and ANSI colors for console."""

    COLORS = {
        logging.DEBUG: "\033[36m",  # Cyan
        logging.INFO: "\033[32m",  # Green
        logging.WARNING: "\033[33m",  # Yellow
        logging.ERROR: "\033[31m",  # Red
        logging.CRITICAL: "\033[1;31m",  # Bold Red
    }
    RESET = "\033[0m"

    def __init__(self, json_mode: bool = False, include_extra: bool = True) -> None:
        super().__init__()
        self.json_mode = json_mode
        self.include_extra = include_extra

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON or human-readable colorized string."""
        iso_timestamp = datetime.fromtimestamp(record.created, tz=UTC).isoformat()

        if self.json_mode:
            log_payload: dict[str, Any] = {
                "timestamp": iso_timestamp,
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "module": record.module,
                "line": record.lineno,
            }

            # Capture extra contextual attributes (e.g. node_id, core_id, run_id, op)
            if self.include_extra:
                for key, val in record.__dict__.items():
                    if key not in (
                        "name",
                        "msg",
                        "args",
                        "levelname",
                        "levelno",
                        "pathname",
                        "filename",
                        "module",
                        "exc_info",
                        "exc_text",
                        "stack_info",
                        "lineno",
                        "funcName",
                        "created",
                        "msecs",
                        "relativeCreated",
                        "thread",
                        "threadName",
                        "processName",
                        "process",
                        "message",
                    ):
                        log_payload[key] = val

            if record.exc_info:
                log_payload["exception"] = self.formatException(record.exc_info)

            return json.dumps(log_payload, separators=(",", ":"))

        # ANSI Console Mode
        color = self.COLORS.get(record.levelno, "")
        reset = self.RESET if color else ""
        msg = record.getMessage()

        context_tags = []
        if hasattr(record, "node_id"):
            context_tags.append(f"node={record.node_id}")
        if hasattr(record, "core_id"):
            context_tags.append(f"core={record.core_id}")
        if hasattr(record, "run_id"):
            context_tags.append(f"run={record.run_id}")

        tag_str = f" [{', '.join(context_tags)}]" if context_tags else ""
        lvl_str = f"{color}[{record.levelname:<7}]{reset}"
        formatted = f"{iso_timestamp} {lvl_str} {record.name}{tag_str}: {msg}"

        if record.exc_info:
            formatted += f"\n{self.formatException(record.exc_info)}"

        return formatted
