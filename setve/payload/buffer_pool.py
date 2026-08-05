"""Page-Aligned mmap Ring Buffer Allocator."""

import ctypes
import mmap
import os
import sys
from typing import List

from setve.adapters.base import DirectBuffer


class BufferPool:
    """Pre-allocated anonymous page-aligned mmap ring buffer pool."""

    def __init__(self, buffer_count: int = 16, buffer_size: int = 1048576) -> None:
        self.buffer_count = buffer_count
        self.buffer_size = buffer_size
        self._buffers: List[DirectBuffer] = []
        self._allocate_pool()

    def _allocate_pool(self) -> None:
        """Pre-allocate page-aligned anonymous mmap memory blocks."""
        for _ in range(self.buffer_count):
            if sys.platform == "win32":
                # Windows anonymous mmap (backed by pagefile)
                buf = mmap.mmap(-1, self.buffer_size)
            else:
                # Unix/Linux anonymous mmap
                flags = getattr(mmap, "MAP_PRIVATE", 0) | getattr(mmap, "MAP_ANONYMOUS", 0)
                if flags == 0:
                    buf = mmap.mmap(-1, self.buffer_size)
                else:
                    buf = mmap.mmap(-1, self.buffer_size, flags=flags)
            
            # Fetch absolute memory address via ctypes to enable hardware alignment assertions
            address = ctypes.addressof(ctypes.c_char.from_buffer(buf))
            view = memoryview(buf)
            
            self._buffers.append(
                DirectBuffer(
                    address=address,
                    size=self.buffer_size,
                    view=view,
                )
            )

    def acquire(self, index: int) -> DirectBuffer:
        """Acquire pre-allocated buffer slice by index."""
        return self._buffers[index % len(self._buffers)]
