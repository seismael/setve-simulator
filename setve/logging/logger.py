"""Zero-Overhead Contextual Structured Logger Wrapper."""

from __future__ import annotations

import logging
from typing import Any


class SetveLogger:
    """Zero-overhead contextual structured logger for SETVE core engines."""

    def __init__(self, name: str, context: dict[str, Any] | None = None) -> None:
        self._logger = logging.getLogger(name)
        self._context = context.copy() if context else {}

    def with_context(self, **kwargs: Any) -> SetveLogger:
        """Return a new logger instance inheriting parent context merged with new attributes."""
        merged = self._context.copy()
        merged.update(kwargs)
        return SetveLogger(self._logger.name, merged)

    @property
    def is_debug_enabled(self) -> bool:
        """Fast O(1) check if DEBUG logging is enabled, avoiding hot-path formatting."""
        return self._logger.isEnabledFor(logging.DEBUG)

    @property
    def is_info_enabled(self) -> bool:
        """Fast O(1) check if INFO logging is enabled."""
        return self._logger.isEnabledFor(logging.INFO)

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Emit DEBUG log message if enabled, appending contextual attributes."""
        if self.is_debug_enabled:
            extra = self._context.copy()
            if "extra" in kwargs:
                extra.update(kwargs.pop("extra"))
            self._logger.debug(msg, *args, extra=extra, **kwargs)

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Emit INFO log message."""
        if self.is_info_enabled:
            extra = self._context.copy()
            if "extra" in kwargs:
                extra.update(kwargs.pop("extra"))
            self._logger.info(msg, *args, extra=extra, **kwargs)

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Emit WARNING log message."""
        extra = self._context.copy()
        if "extra" in kwargs:
            extra.update(kwargs.pop("extra"))
        self._logger.warning(msg, *args, extra=extra, **kwargs)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Emit ERROR log message."""
        extra = self._context.copy()
        if "extra" in kwargs:
            extra.update(kwargs.pop("extra"))
        self._logger.error(msg, *args, extra=extra, **kwargs)

    def critical(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Emit CRITICAL log message."""
        extra = self._context.copy()
        if "extra" in kwargs:
            extra.update(kwargs.pop("extra"))
        self._logger.critical(msg, *args, extra=extra, **kwargs)

    def exception(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Emit ERROR log message with stack trace."""
        extra = self._context.copy()
        if "extra" in kwargs:
            extra.update(kwargs.pop("extra"))
        self._logger.exception(msg, *args, extra=extra, **kwargs)
