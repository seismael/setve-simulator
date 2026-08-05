"""POSIX Direct I/O (O_DIRECT) Storage Target Adapter."""

import asyncio
import os
from typing import Any, Dict

from setve.adapters.base import (
    AdapterCapabilities,
    DirectBuffer,
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
        self.fd = -1

    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize POSIX adapter resources."""
        pass

    def _open(self, target: TargetDescriptor) -> None:
        if self.fd == -1:
            flags = os.O_WRONLY | os.O_CREAT
            if hasattr(os, "O_DIRECT"):
                flags |= getattr(os, "O_DIRECT")
            if hasattr(os, "O_BINARY"):
                flags |= getattr(os, "O_BINARY")
            self.fd = os.open(target.resource_path, flags, 0o666)

    async def write(self, target: TargetDescriptor, offset: int, payload: DirectBuffer) -> int:
        """Execute Direct I/O write enforcing 4096-byte alignment."""
        payload.assert_alignment(4096)
        if self.fd == -1:
            self._open(target)
            
        loop = asyncio.get_running_loop()
        def _do_write() -> int:
            os.lseek(self.fd, offset, os.SEEK_SET)
            return os.write(self.fd, payload.view)
            
        return await loop.run_in_executor(None, _do_write)

    async def read(self, target: TargetDescriptor, offset: int, buffer: DirectBuffer) -> int:
        """Execute Direct I/O read enforcing 4096-byte alignment."""
        buffer.assert_alignment(4096)
        if self.fd == -1:
            self._open(target)
            
        loop = asyncio.get_running_loop()
        def _do_read() -> int:
            os.lseek(self.fd, offset, os.SEEK_SET)
            return os.read(self.fd, buffer.view.nbytes)
            
        return await loop.run_in_executor(None, _do_read)

    async def flush(self, target: TargetDescriptor) -> None:
        """Flush file sync state."""
        if self.fd != -1:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, lambda: os.fsync(self.fd))

    def close(self) -> None:
        """Close file descriptor."""
        if self.fd != -1:
            os.close(self.fd)
            self.fd = -1

    def capabilities(self) -> AdapterCapabilities:
        """Return adapter capabilities."""
        return self._capabilities
