"""Asynchronous Non-Blocking Multiprocess Log Queue Handler."""

from __future__ import annotations

import logging
import multiprocessing as mp
from logging.handlers import QueueHandler
from typing import Any


class AsyncLogQueueHandler(QueueHandler):
    """Log handler that routes log records asynchronously into a multiprocessing queue."""

    def __init__(self, queue: mp.Queue[Any]) -> None:
        super().__init__(queue)

    def prepare(self, record: logging.LogRecord) -> logging.LogRecord:
        """Format exception info into string before serialization across process boundaries."""
        if record.exc_info:
            record.exc_text = logging.Formatter().formatException(record.exc_info)
            record.exc_info = None
        if record.args:
            record.msg = record.getMessage()
            record.args = None
        return record
