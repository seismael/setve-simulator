"""TargetAdapter Abstract Base Class and DirectBuffer Data Transfer Contracts."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from steve.exceptions import (
    AdapterError,
    AdapterInitializationError,
    AdapterNotImplementedError,
    AlignmentError,
    ConnectionTimeoutError,
    DeviceNotFoundError,
    HardwareIoError,
    MisalignedBufferError,
    MisalignedLengthError,
    MisalignedOffsetError,
    QueueFullError,
    SetveError,
    SteveError,
    StorageExhaustedError,
)

__all__ = [
    "AdapterCapabilities",
    "AdapterError",
    "AdapterInitializationError",
    "AdapterNotImplementedError",
    "AlignmentError",
    "ConnectionTimeoutError",
    "DeviceNotFoundError",
    "DirectBuffer",
    "HardwareIoError",
    "MisalignedBufferError",
    "MisalignedLengthError",
    "MisalignedOffsetError",
    "QueueFullError",
    "SetveError",
    "SteveError",
    "StorageExhaustedError",
    "TargetAdapter",
    "TargetDescriptor",
]


@dataclass(slots=True)
class DirectBuffer:
    """Page-aligned memory buffer wrapper for Direct I/O operations."""

    address: int
    size: int
    view: memoryview

    def assert_alignment(self, alignment: int = 4096) -> None:
        """Assert that buffer address is aligned to specified byte boundary."""
        if self.address % alignment != 0:
            raise MisalignedBufferError(
                f"DirectBuffer at address {hex(self.address)} violates {alignment}-byte alignment"
            )


@dataclass(slots=True)
class TargetDescriptor:
    """Descriptor identifying target storage or communication resource."""

    endpoint_uri: str
    resource_path: str


@dataclass(slots=True)
class AdapterCapabilities:
    """Defines operational capabilities of a TargetAdapter implementation."""

    supports_direct_io: bool
    supports_async_cancellation: bool
    max_concurrent_ops: int
    native_block_size: int


class TargetAdapter(ABC):
    """Abstract Base Class for all STEVE storage and protocol drivers."""

    @abstractmethod
    async def initialize(self, config: dict[str, Any]) -> None:
        """Initialize adapter resources and handle configurations."""
        ...

    @abstractmethod
    async def write(self, target: TargetDescriptor, offset: int, payload: DirectBuffer) -> int:
        """Submit non-blocking write operation using DirectBuffer payload."""
        ...

    @abstractmethod
    async def read(self, target: TargetDescriptor, offset: int, buffer: DirectBuffer) -> int:
        """Submit non-blocking read operation into target DirectBuffer."""
        ...

    @abstractmethod
    async def flush(self, target: TargetDescriptor) -> None:
        """Flush any pending in-flight writes to target storage medium."""
        ...

    @abstractmethod
    def capabilities(self) -> AdapterCapabilities:
        """Return adapter operational capabilities."""
        ...
