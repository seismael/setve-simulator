"""Structured Logging & Observability Verification Suite."""

from __future__ import annotations

import io
import json
import logging
import multiprocessing as mp

from setve.logging import configure_logging, get_logger
from setve.logging.async_handler import AsyncLogQueueHandler
from setve.logging.formatter import StructuredLogFormatter


def test_structured_json_formatting() -> None:
    """Verify that StructuredLogFormatter emits valid JSON records with contextual attributes."""
    formatter = StructuredLogFormatter(json_mode=True)
    record = logging.LogRecord(
        name="setve.test",
        level=logging.INFO,
        pathname="test.py",
        lineno=42,
        msg="Benchmark execution milestone reached",
        args=(),
        exc_info=None,
    )
    record.node_id = "node-alpha"  # type: ignore[attr-defined]
    record.core_id = 7  # type: ignore[attr-defined]
    record.run_id = "sim-run-99"  # type: ignore[attr-defined]

    formatted = formatter.format(record)
    parsed = json.loads(formatted)

    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "setve.test"
    assert parsed["message"] == "Benchmark execution milestone reached"
    assert parsed["node_id"] == "node-alpha"
    assert parsed["core_id"] == 7
    assert parsed["run_id"] == "sim-run-99"
    assert "timestamp" in parsed


def test_setve_logger_context_inheritance() -> None:
    """Verify that SetveLogger.with_context creates child loggers with merged metadata."""
    stream = io.StringIO()
    handler = configure_logging(level=logging.DEBUG, json_mode=True, stream=stream)

    try:
        parent_logger = get_logger("setve.orchestrator", node_id="node-01")
        child_logger = parent_logger.with_context(core_id=3, operation="direct_io_write")

        child_logger.info("Starting worker thread execution")
        handler.flush()

        output = stream.getvalue().strip()
        parsed = json.loads(output)

        assert parsed["node_id"] == "node-01"
        assert parsed["core_id"] == 3
        assert parsed["operation"] == "direct_io_write"
        assert parsed["message"] == "Starting worker thread execution"
    finally:
        logging.getLogger("setve").removeHandler(handler)


def test_setve_logger_level_gating() -> None:
    """Verify is_debug_enabled fast-path check prevents string formatting when debug is disabled."""
    logger = get_logger("setve.bench")
    logging.getLogger("setve").setLevel(logging.WARNING)

    assert not logger.is_debug_enabled
    assert not logger.is_info_enabled

    logging.getLogger("setve").setLevel(logging.DEBUG)
    assert logger.is_debug_enabled
    assert logger.is_info_enabled


def test_async_log_queue_handler_propagation() -> None:
    """Verify that AsyncLogQueueHandler cleanly ships records across multiprocessing queue."""
    queue: mp.Queue[logging.LogRecord] = mp.Queue()
    handler = AsyncLogQueueHandler(queue)

    record = logging.LogRecord(
        name="setve.worker",
        level=logging.ERROR,
        pathname="worker.py",
        lineno=100,
        msg="Storage queue %s was saturated",
        args=(12,),
        exc_info=None,
    )

    handler.emit(record)
    popped = queue.get(timeout=2.0)
    assert popped.name == "setve.worker"
    assert popped.msg == "Storage queue 12 was saturated"
