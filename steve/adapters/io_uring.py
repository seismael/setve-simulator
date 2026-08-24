"""Linux io_uring Target Adapter Implementation for Zero-Copy Direct I/O."""

import os
import sys
from pathlib import Path
from typing import Any, Final

from steve.adapters.base import (
    AdapterCapabilities,
    AdapterError,
    AlignmentError,
    DirectBuffer,
    HardwareIoError,
    QueueFullError,
    TargetAdapter,
    TargetDescriptor,
)

ALIGNMENT_BLOCK_SIZE: Final[int] = 4096

# Platform conditional import of liburing structures
try:
    if sys.platform == "linux":
        from liburing import (  # type: ignore[import-untyped, import-not-found]
            Cqe,
            Ring,
            io_uring_cqe_seen,
            io_uring_get_sqe,
            io_uring_prep_read,
            io_uring_prep_write,
            io_uring_queue_exit,
            io_uring_queue_init,
            io_uring_submit,
            io_uring_wait_cqe,
        )
    else:
        Ring = None
        Cqe = None
        io_uring_queue_init: Any = None
except ImportError:
    Ring = None
    Cqe = None
    io_uring_queue_init = None


class IoUringTargetAdapter(TargetAdapter):
    """Linux io_uring target adapter utilizing kernel-bypass zero-copy memory transfers."""

    def __init__(self, queue_depth: int = 1024) -> None:
        self.queue_depth: int = queue_depth
        self._initialized: bool = False
        self._ring: Any = Ring() if Ring is not None else None
        self._cqe: Any = Cqe() if Cqe is not None else None
        self._fds: dict[str, int] = {}
        self._capabilities: AdapterCapabilities = AdapterCapabilities(
            supports_direct_io=True,
            supports_async_cancellation=True,
            max_concurrent_ops=queue_depth,
            native_block_size=ALIGNMENT_BLOCK_SIZE,
        )

    async def initialize(self, config: dict[str, Any]) -> None:
        """Initialize Linux io_uring submission/completion rings."""
        if self._initialized:
            return

        if sys.platform != "linux" or Ring is None or io_uring_queue_init is None:
            # Emulated / Mock mode on non-Linux platforms
            self._initialized = True
            return

        res = io_uring_queue_init(self.queue_depth, self._ring, 0)
        if res < 0:
            raise AdapterError(f"Failed to initialize io_uring ring: {os.strerror(-res)}")

        self._initialized = True

    def _verify_alignment(self, buffer: DirectBuffer, offset: int) -> None:
        """Validate 4096-byte Direct I/O alignment boundaries."""
        if buffer.address % ALIGNMENT_BLOCK_SIZE != 0:
            raise AlignmentError(
                f"Buffer address {hex(buffer.address)} violates "
                f"{ALIGNMENT_BLOCK_SIZE}-byte page boundary"
            )
        if buffer.size % ALIGNMENT_BLOCK_SIZE != 0:
            raise AlignmentError(
                f"Buffer length {buffer.size} is not a multiple of {ALIGNMENT_BLOCK_SIZE} bytes"
            )
        if offset % ALIGNMENT_BLOCK_SIZE != 0:
            raise AlignmentError(
                f"File offset {offset} is not a multiple of {ALIGNMENT_BLOCK_SIZE} bytes"
            )

    def _get_or_open_fd(self, target: TargetDescriptor) -> int:
        """Retrieve or open file descriptor for the specified target resource."""
        path = target.resource_path
        if path in self._fds:
            return self._fds[path]

        parent_dir = Path(path).parent
        if parent_dir and not parent_dir.exists():
            parent_dir.mkdir(parents=True, exist_ok=True)

        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_DIRECT"):
            flags |= os.O_DIRECT
        if hasattr(os, "O_BINARY"):
            flags |= os.O_BINARY

        try:
            fd = os.open(path, flags, 0o666)
        except OSError as e:
            raise AdapterError(f"Failed to open target {path}: {e}") from e

        self._fds[path] = fd
        return fd

    async def write(self, target: TargetDescriptor, offset: int, payload: DirectBuffer) -> int:
        """Submit SQE write pointing directly to DirectBuffer memoryview."""
        if not self._initialized:
            await self.initialize({})

        self._verify_alignment(payload, offset)
        fd = self._get_or_open_fd(target)

        if sys.platform == "linux" and self._ring is not None:
            sqe = io_uring_get_sqe(self._ring)
            if not sqe:
                io_uring_submit(self._ring)
                sqe = io_uring_get_sqe(self._ring)
                if not sqe:
                    raise QueueFullError("io_uring submission queue saturated")

            io_uring_prep_write(sqe, fd, payload.view, offset)
            sqe.user_data = 1

            submitted = io_uring_submit(self._ring)
            if submitted < 0:
                raise AdapterError(f"io_uring_submit failed: {os.strerror(-submitted)}")

            io_uring_wait_cqe(self._ring, self._cqe)
            cqe_entry = self._cqe[0]
            result = int(cqe_entry.res)

            if result < 0:
                raise HardwareIoError(f"io_uring Direct I/O write failed: {os.strerror(-result)}")

            io_uring_cqe_seen(self._ring, cqe_entry)
            return result

        # Non-Linux fallback emulation
        os.lseek(fd, offset, os.SEEK_SET)
        return os.write(fd, payload.view)

    async def read(self, target: TargetDescriptor, offset: int, buffer: DirectBuffer) -> int:
        """Submit SQE read into target DirectBuffer."""
        if not self._initialized:
            await self.initialize({})

        self._verify_alignment(buffer, offset)
        fd = self._get_or_open_fd(target)

        if sys.platform == "linux" and self._ring is not None:
            sqe = io_uring_get_sqe(self._ring)
            if not sqe:
                io_uring_submit(self._ring)
                sqe = io_uring_get_sqe(self._ring)
                if not sqe:
                    raise QueueFullError("io_uring submission queue saturated")

            io_uring_prep_read(sqe, fd, buffer.view, offset)
            sqe.user_data = 2

            submitted = io_uring_submit(self._ring)
            if submitted < 0:
                raise AdapterError(f"io_uring_submit failed: {os.strerror(-submitted)}")

            io_uring_wait_cqe(self._ring, self._cqe)
            cqe_entry = self._cqe[0]
            result = int(cqe_entry.res)

            if result < 0:
                raise HardwareIoError(f"io_uring Direct I/O read failed: {os.strerror(-result)}")

            io_uring_cqe_seen(self._ring, cqe_entry)
            return result

        # Non-Linux fallback emulation
        os.lseek(fd, offset, os.SEEK_SET)
        data = os.read(fd, buffer.size)
        buffer.view[: len(data)] = data
        return len(data)

    async def flush(self, target: TargetDescriptor) -> None:
        """Flush io_uring submission queue and sync file descriptors."""
        if sys.platform == "linux" and self._ring is not None and self._initialized:
            io_uring_submit(self._ring)

        path = target.resource_path
        if path in self._fds:
            import contextlib

            with contextlib.suppress(OSError):
                os.fsync(self._fds[path])

    def capabilities(self) -> AdapterCapabilities:
        """Return adapter capabilities."""
        return self._capabilities

    def close(self) -> None:
        """Close io_uring ring and all file descriptors."""
        import contextlib

        for _path, fd in list(self._fds.items()):
            with contextlib.suppress(OSError):
                os.close(fd)
        self._fds.clear()

        if sys.platform == "linux" and self._ring is not None and self._initialized:
            io_uring_queue_exit(self._ring)
            self._initialized = False
