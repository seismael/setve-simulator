"""Unified Domain Exception Hierarchy and OS Errno Translation Engine for STEVE."""

from __future__ import annotations

import errno


class SteveError(Exception):
    """Base exception for all STEVE simulation and validation errors."""

    @classmethod
    def from_errno(cls, err: OSError, context: str = "") -> SteveError:
        """Map raw OS errno error code to granular domain-specific SteveError subclass."""
        err_no = err.errno if err.errno is not None else 0
        detail = f"{context}: {err}" if context else str(err)

        if err_no == errno.EINVAL:
            return MisalignedOffsetError(f"Invalid argument or misaligned I/O boundary: {detail}")
        if err_no == errno.ENOSPC:
            return StorageExhaustedError(f"Storage capacity exhausted (no space left): {detail}")
        if err_no in (errno.EIO, getattr(errno, "EBADFD", 77)):
            return HardwareIoError(f"Hardware/Device I/O fault encountered: {detail}")
        if err_no in (errno.EACCES, errno.EPERM):
            return AdapterError(f"Permission denied accessing target storage resource: {detail}")
        if err_no in (errno.ENOENT, errno.ENXIO, errno.ENODEV):
            return DeviceNotFoundError(f"Target storage device or file not found: {detail}")
        if err_no in (errno.ETIMEDOUT, errno.ECONNREFUSED, errno.EHOSTUNREACH):
            return ConnectionTimeoutError(f"Network transport connection timeout: {detail}")

        return HardwareIoError(f"Operating system I/O error (errno={err_no}): {detail}")


# Backward-compatible alias
SetveError = SteveError


# ---------------------------------------------------------
# Storage & Adapter Exceptions
# ---------------------------------------------------------


class AdapterError(SteveError):
    """Base exception for storage adapter and transport driver failures."""


class AdapterInitializationError(AdapterError):
    """Raised when an adapter fails to initialize its resources or kernel channels."""


class AdapterNotImplementedError(AdapterError, NotImplementedError):
    """Raised when an adapter method or scheme is unsupported on the host platform."""


class HardwareIoError(AdapterError):
    """Raised when an underlying I/O device or interface returns an I/O fault."""


class DeviceNotFoundError(HardwareIoError):
    """Raised when a requested storage device, block mount, or file target does not exist."""


class StorageExhaustedError(HardwareIoError):
    """Raised when the target storage volume runs out of free capacity (ENOSPC)."""


class QueueFullError(AdapterError):
    """Raised when an adapter's submission queue (SQ) is saturated."""


class ConnectionTimeoutError(AdapterError):
    """Raised when an out-of-band or network target transport connection times out."""


# ---------------------------------------------------------
# Alignment & Memory Layout Exceptions
# ---------------------------------------------------------


class AlignmentError(SteveError, ValueError):
    """Base exception for hardware alignment violations (addresses, offsets, sizes)."""


class MisalignedBufferError(AlignmentError):
    """Raised when a memory buffer's base address violates hardware alignment (e.g. 4096B)."""


class MisalignedOffsetError(AlignmentError):
    """Raised when a file or block offset violates hardware block alignment."""


class MisalignedLengthError(AlignmentError):
    """Raised when a payload transfer length is not an exact multiple of the block boundary."""


# ---------------------------------------------------------
# Payload Engine & Buffer Pool Exceptions
# ---------------------------------------------------------


class PayloadError(SteveError, ValueError):
    """Base exception for payload generation and entropy mutation errors."""


class BufferPoolExhaustedError(PayloadError):
    """Raised when the buffer pool cannot allocate or acquire an available buffer."""


class BufferAllocationError(PayloadError):
    """Raised when anonymous mmap or memory allocation fails."""


class InvalidEntropyError(PayloadError):
    """Raised when an entropy ratio parameter falls outside the valid [0.0, 1.0] range."""


# ---------------------------------------------------------
# Multi-Process Control Plane & Orchestrator Exceptions
# ---------------------------------------------------------


class OrchestratorError(SteveError):
    """Base exception for multi-process control plane failures."""


class WorkerCrashError(OrchestratorError):
    """Raised when a core-pinned worker process crashes or exits with non-zero exit code."""


class ClusterSyncTimeoutError(OrchestratorError):
    """Raised when distributed nodes fail to reach a barrier synchronization point."""


class TopologyError(OrchestratorError):
    """Raised when CPU core affinity mapping or node topology is invalid."""


# ---------------------------------------------------------
# Validation & Telemetry Exceptions
# ---------------------------------------------------------


class ValidationPlaneError(SteveError):
    """Base exception for metric collection and telemetry triangulation failures."""


class TelemetryDivergenceError(ValidationPlaneError):
    """Raised when client metrics diverge beyond the acceptable tolerance threshold."""


class MetricCollectorError(ValidationPlaneError):
    """Raised when metric aggregation encounters corrupted or invalid bucket data."""
