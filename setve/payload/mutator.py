"""AVX-512 accelerated in-place payload mutation engine."""

import ctypes
import mmap
import sys

import numpy as np

from setve.adapters.base import DirectBuffer


class PySIMDPayloadMutator:
    """Dynamically mutates data buffers in-place using SIMD/NumPy to defeat deduplication."""

    def __init__(self, buffer_size: int, alignment: int = 4096) -> None:
        self.size = buffer_size
        self.alignment = alignment

        if sys.platform == "win32":
            self.buffer = mmap.mmap(-1, self.size)
        else:
            flags = getattr(mmap, "MAP_PRIVATE", 0) | getattr(mmap, "MAP_ANONYMOUS", 0)
            if flags == 0:
                self.buffer = mmap.mmap(-1, self.size)
            else:
                self.buffer = mmap.mmap(-1, self.size, flags=flags)

        self.address = ctypes.addressof(ctypes.c_char.from_buffer(self.buffer))
        self.view = memoryview(self.buffer)
        self._cached_direct_buffer: DirectBuffer | None = None

    def apply_entropy(self, offset: int, block_size: int, seed: int) -> DirectBuffer:
        """Applies a deterministic seed-based entropy mask in-place using SIMD."""
        if offset + block_size > self.size:
            raise ValueError(
                f"Requested slice [{offset}:{offset + block_size}] exceeds buffer size {self.size}"
            )

        block_view = self.view[offset : offset + block_size]

        # Vectorized 64-bit SIMD in-place mutation using NumPy buffer view (Zero allocation)
        if len(block_view) >= 8:
            uint64_count = len(block_view) // 8
            # In-place array view over memoryview
            np_arr = np.frombuffer(block_view[: uint64_count * 8], dtype=np.uint64)
            mask = np.uint64(seed ^ 0x5555555555555555)
            np_arr ^= mask

        slice_address = self.address + offset
        return DirectBuffer(
            address=slice_address,
            size=block_size,
            view=block_view,
        )

    def mutate_entropy_block(
        self, offset: int, length: int, entropy_ratio: float = 0.8, seed: int = 42
    ) -> DirectBuffer:
        """Mutate a block with a given entropy ratio according to SPEC blueprint."""
        if offset + length > self.size:
            raise ValueError(f"Requested block [{offset}:{offset + length}] exceeds {self.size}")

        block_view = self.view[offset : offset + length]

        if len(block_view) >= 8:
            uint64_count = len(block_view) // 8
            np_arr = np.frombuffer(block_view[: uint64_count * 8], dtype=np.uint64)
            # Mutate proportional elements according to entropy_ratio
            mutate_elements = int(uint64_count * min(max(entropy_ratio, 0.0), 1.0))
            if mutate_elements > 0:
                mask = np.uint64(seed ^ 0x9E3779B97F4A7C15)
                np_arr[:mutate_elements] ^= mask

        slice_address = self.address + offset
        return DirectBuffer(
            address=slice_address,
            size=length,
            view=block_view,
        )

    def close(self) -> None:
        """Release mmap resources."""
        import contextlib

        if hasattr(self, "view"):
            with contextlib.suppress(Exception):
                self.view.release()
            del self.view
        with contextlib.suppress(BufferError, OSError):
            self.buffer.close()

