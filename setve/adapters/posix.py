"""POSIX Direct I/O (O_DIRECT) Storage Target Adapter."""

from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Any

from setve.adapters.base import (
    AdapterCapabilities,
    DirectBuffer,
    SetveError,
    TargetAdapter,
    TargetDescriptor,
)


class PosixDirectIOAdapter(TargetAdapter):
    """Direct I/O file adapter enforcing O_DIRECT flag and block alignment."""

    def __init__(self) -> None:
        self._capabilities = AdapterCapabilities(
            supports_direct_io=True,
            supports_async_cancellation=False,
            max_concurrent_ops=64,
            native_block_size=4096,
        )
        self._fds: dict[str, int] = {}
        self._file_ios: dict[str, io.FileIO] = {}

    async def initialize(self, config: dict[str, Any]) -> None:
        """Initialize POSIX adapter resources."""
        pass

    def _get_or_open_fd(self, target: TargetDescriptor) -> int:
        """Retrieve or open file descriptor for the specified target resource."""
        path = target.resource_path
        if path in self._fds:
            return self._fds[path]

        # Ensure parent directory exists
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
            raise SetveError.from_errno(e, f"Failed to open target {path}") from e

        self._fds[path] = fd
        self._file_ios[path] = io.FileIO(fd, mode="r+", closefd=False)
        return fd

    async def write(self, target: TargetDescriptor, offset: int, payload: DirectBuffer) -> int:
        """Execute Direct I/O write enforcing 4096-byte alignment."""
        payload.assert_alignment(4096)
        fd = self._get_or_open_fd(target)

        try:
            os.lseek(fd, offset, os.SEEK_SET)
            written = os.write(fd, payload.view)
            return written
        except OSError as e:
            err_ctx = f"POSIX Direct I/O write failed at offset {offset}"
            raise SetveError.from_errno(e, err_ctx) from e

    async def read(self, target: TargetDescriptor, offset: int, buffer: DirectBuffer) -> int:
        """Execute Direct I/O read enforcing 4096-byte alignment directly into DirectBuffer.view."""
        buffer.assert_alignment(4096)
        fd = self._get_or_open_fd(target)
        path = target.resource_path

        try:
            # 1. Zero-copy readv (Linux / BSD)
            if hasattr(os, "readv"):
                os.lseek(fd, offset, os.SEEK_SET)
                readv_fn: Any = getattr(os, "readv")  # noqa: B009
                return int(readv_fn(fd, [buffer.view]))

            # 2. Zero-allocation readinto using cached FileIO handle
            f = self._file_ios[path]
            f.seek(offset, os.SEEK_SET)
            bytes_read = f.readinto(buffer.view)
            return bytes_read if bytes_read is not None else 0
        except OSError as e:
            err_ctx = f"POSIX Direct I/O read failed at offset {offset}"
            raise SetveError.from_errno(e, err_ctx) from e

    async def flush(self, target: TargetDescriptor) -> None:
        """Flush file sync state."""
        path = target.resource_path
        if path in self._fds:
            try:
                os.fsync(self._fds[path])
            except OSError as e:
                raise SetveError.from_errno(e, f"POSIX flush failed for {path}") from e

    def close(self) -> None:
        """Close all open file descriptors and streams."""
        import contextlib

        for f in list(self._file_ios.values()):
            with contextlib.suppress(Exception):
                f.close()
        self._file_ios.clear()

        for _path, fd in list(self._fds.items()):
            with contextlib.suppress(OSError):
                os.close(fd)
        self._fds.clear()

    def capabilities(self) -> AdapterCapabilities:
        """Return adapter capabilities."""
        return self._capabilities
