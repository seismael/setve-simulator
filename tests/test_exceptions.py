"""Tests for STEVE Exception taxonomy and error handling contracts."""

import errno

import pytest

from steve.exceptions import (
    AdapterError,
    AdapterInitializationError,
    AdapterNotImplementedError,
    AlignmentError,
    BufferPoolExhaustedError,
    ClusterSyncTimeoutError,
    ConnectionTimeoutError,
    DeviceNotFoundError,
    HardwareIoError,
    InvalidEntropyError,
    MisalignedBufferError,
    MisalignedLengthError,
    MisalignedOffsetError,
    OrchestratorError,
    PayloadError,
    QueueFullError,
    SetveError,
    SteveError,
    StorageExhaustedError,
    TelemetryDivergenceError,
    WorkerCrashError,
)


def test_exception_hierarchy() -> None:
    """Verify all domain errors inherit properly from SteveError base."""
    # Base alias
    assert issubclass(SetveError, SteveError)

    # Storage & Adapter hierarchy
    assert issubclass(AdapterError, SteveError)
    assert issubclass(AdapterInitializationError, AdapterError)
    assert issubclass(AdapterNotImplementedError, AdapterError)
    assert issubclass(AdapterNotImplementedError, NotImplementedError)
    assert issubclass(HardwareIoError, AdapterError)
    assert issubclass(DeviceNotFoundError, HardwareIoError)
    assert issubclass(StorageExhaustedError, HardwareIoError)
    assert issubclass(QueueFullError, AdapterError)
    assert issubclass(ConnectionTimeoutError, AdapterError)

    # Alignment hierarchy
    assert issubclass(AlignmentError, SteveError)
    assert issubclass(AlignmentError, ValueError)
    assert issubclass(MisalignedBufferError, AlignmentError)
    assert issubclass(MisalignedOffsetError, AlignmentError)
    assert issubclass(MisalignedLengthError, AlignmentError)

    # Payload & Buffer hierarchy
    assert issubclass(PayloadError, SteveError)
    assert issubclass(BufferPoolExhaustedError, PayloadError)
    assert issubclass(InvalidEntropyError, PayloadError)

    # Orchestrator & Control plane hierarchy
    assert issubclass(OrchestratorError, SteveError)
    assert issubclass(WorkerCrashError, OrchestratorError)
    assert issubclass(ClusterSyncTimeoutError, OrchestratorError)

    # Validation hierarchy
    assert issubclass(TelemetryDivergenceError, SteveError)


def test_from_errno_mapping() -> None:
    """Verify SteveError.from_errno accurately translates POSIX error codes."""
    # EINVAL -> MisalignedOffsetError
    err_inval = SteveError.from_errno(
        OSError(errno.EINVAL, "Invalid argument"), context="Direct I/O"
    )
    assert isinstance(err_inval, MisalignedOffsetError)
    assert "Direct I/O" in str(err_inval)

    # ENOSPC -> StorageExhaustedError
    err_nospc = SteveError.from_errno(OSError(errno.ENOSPC, "No space left on device"))
    assert isinstance(err_nospc, StorageExhaustedError)

    # EIO -> HardwareIoError
    err_io = SteveError.from_errno(OSError(errno.EIO, "Input/output error"))
    assert isinstance(err_io, HardwareIoError)

    # ENOENT -> DeviceNotFoundError
    err_noent = SteveError.from_errno(OSError(errno.ENOENT, "No such file or directory"))
    assert isinstance(err_noent, DeviceNotFoundError)

    # EACCES -> AdapterError
    err_acces = SteveError.from_errno(OSError(errno.EACCES, "Permission denied"))
    assert isinstance(err_acces, AdapterError)

    # ETIMEDOUT -> ConnectionTimeoutError
    err_timeout = SteveError.from_errno(OSError(errno.ETIMEDOUT, "Connection timed out"))
    assert isinstance(err_timeout, ConnectionTimeoutError)


def test_exception_instantiation_and_catch() -> None:
    """Verify specific errors can be caught as general SteveError and AdapterError."""
    with pytest.raises(SteveError):
        raise MisalignedBufferError("Alignment 4096 violation")

    with pytest.raises(SetveError):
        raise MisalignedBufferError("Alignment 4096 violation (SetveError alias)")

    with pytest.raises(AdapterError):
        raise QueueFullError("Submission queue depth 1024 saturated")

    with pytest.raises(OrchestratorError):
        raise WorkerCrashError("Worker on core 3 crashed with SIGSEGV")

    with pytest.raises(PayloadError):
        raise InvalidEntropyError("Entropy ratio 1.5 exceeds 1.0 bound")
