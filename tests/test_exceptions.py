"""Tests for SETVE Exception taxonomy and error handling contracts."""

import pytest

from setve.adapters.base import (
    AdapterError,
    AlignmentError,
    HardwareIoError,
    QueueFullError,
)


def test_exception_hierarchy() -> None:
    """Verify all domain errors inherit properly from AdapterError."""
    assert issubclass(AlignmentError, AdapterError)
    assert issubclass(AlignmentError, ValueError)
    assert issubclass(QueueFullError, AdapterError)
    assert issubclass(HardwareIoError, AdapterError)


def test_exception_instantiation_and_catch() -> None:
    """Verify specific errors can be caught as general AdapterError."""
    with pytest.raises(AdapterError):
        raise AlignmentError("Alignment 4096 violation")

    with pytest.raises(AdapterError):
        raise QueueFullError("Submission queue depth 1024 saturated")

    with pytest.raises(AdapterError):
        raise HardwareIoError("Physical media I/O fault: EIO")
