"""Page-Aligned mmap Ring Buffer Allocator."""

import ctypes
import mmap
import sys

from steve.adapters.base import DirectBuffer


class BufferPool:
    """Pre-allocated anonymous page-aligned mmap ring buffer pool."""

    def __init__(self, buffer_count: int = 16, buffer_size: int = 1048576) -> None:
        self.buffer_count = buffer_count
        self.buffer_size = buffer_size
        self._mmaps: list[mmap.mmap] = []
        self._buffers: list[DirectBuffer] = []
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

            self._mmaps.append(buf)
            # Fetch absolute memory address via ctypes to enable hardware alignment assertions
            address = ctypes.addressof(ctypes.c_char.from_buffer(buf))
            view = memoryview(buf)

            direct_buf = DirectBuffer(
                address=address,
                size=self.buffer_size,
                view=view,
            )
            direct_buf.assert_alignment(4096)
            self._buffers.append(direct_buf)

    def acquire(self, index: int) -> DirectBuffer:
        """Acquire pre-allocated buffer slice by index."""
        return self._buffers[index % len(self._buffers)]

    def close(self) -> None:
        """Release all allocated mmap memory pools."""
        import contextlib

        for buf in self._buffers:
            if hasattr(buf, "view"):
                with contextlib.suppress(Exception):
                    buf.view.release()
                del buf.view
        self._buffers.clear()

        for m in self._mmaps:
            with contextlib.suppress(BufferError, OSError):
                m.close()
        self._mmaps.clear()
