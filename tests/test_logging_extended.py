"""Extended test suite for structured logging formatters and contextual logger methods."""

import io
import json
import logging

from steve.logging import configure_logging, get_logger
from steve.logging.formatter import StructuredLogFormatter
from steve.logging.logger import SetveLogger, SteveLogger


def test_console_ansi_formatting() -> None:
    """Verify ANSI console log output format, colors, context tags, and exceptions."""
    formatter = StructuredLogFormatter(json_mode=False)

    record = logging.LogRecord(
        name="steve.test.console",
        level=logging.WARNING,
        pathname="test.py",
        lineno=10,
        msg="Disk space low on volume",
        args=(),
        exc_info=None,
    )
    record.node_id = "node-99"
    record.core_id = 4
    record.run_id = "sim-run-123"

    formatted = formatter.format(record)
    assert "node=node-99" in formatted
    assert "core=4" in formatted
    assert "run=sim-run-123" in formatted
    assert "Disk space low on volume" in formatted
    assert "[WARNING]" in formatted


def test_console_exception_formatting() -> None:
    """Verify exception stack traces in console mode and JSON mode."""
    try:
        raise ValueError("Simulated mathematical divergence error")
    except ValueError:
        import sys

        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="steve.test.exc",
        level=logging.ERROR,
        pathname="test.py",
        lineno=25,
        msg="Execution failure during simulation",
        args=(),
        exc_info=exc_info,
    )

    # 1. Console mode with exception
    console_fmt = StructuredLogFormatter(json_mode=False)
    console_out = console_fmt.format(record)
    assert "Execution failure during simulation" in console_out
    assert "Simulated mathematical divergence error" in console_out

    # 2. JSON mode with exception
    json_fmt = StructuredLogFormatter(json_mode=True)
    json_out = json_fmt.format(record)
    parsed = json.loads(json_out)
    assert "exception" in parsed
    assert "Simulated mathematical divergence error" in parsed["exception"]


def test_steve_logger_all_levels() -> None:
    """Verify debug, info, warning, error, critical, and exception logging on SteveLogger."""
    stream = io.StringIO()
    handler = configure_logging(level=logging.DEBUG, json_mode=True, stream=stream)

    try:
        logger = get_logger("steve.levels.test", node_id="node-xyz")
        logger.debug("Debug msg %s", 1)
        logger.info("Info msg %s", 2)
        logger.warning("Warn msg %s", 3)
        logger.error("Error msg %s", 4)
        logger.critical("Critical msg %s", 5)

        try:
            raise RuntimeError("Test crash")
        except RuntimeError:
            logger.exception("Caught exception %s", "runtime")

        handler.flush()
        lines = [json.loads(line) for line in stream.getvalue().strip().split("\n") if line.strip()]

        assert len(lines) == 6
        assert lines[0]["level"] == "DEBUG"
        assert lines[1]["level"] == "INFO"
        assert lines[2]["level"] == "WARNING"
        assert lines[3]["level"] == "ERROR"
        assert lines[4]["level"] == "CRITICAL"
        assert lines[5]["level"] == "ERROR"
        assert "exception" in lines[5]
    finally:
        logging.getLogger("steve").removeHandler(handler)


def test_setve_logger_alias() -> None:
    """Verify SetveLogger is an alias for SteveLogger."""
    assert SetveLogger is SteveLogger
    inst = SetveLogger("steve.alias")
    assert isinstance(inst, SteveLogger)
