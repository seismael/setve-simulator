"""AVX-512 accelerated in-place payload mutation engine."""

import ctypes
import mmap
import sys

import numpy as np

from setve.adapters.base import DirectBuffer
from setve.exceptions import InvalidEntropyError, PayloadError


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
        self._slice_cache: dict[tuple[int, int], DirectBuffer] = {}
        self._primary_direct_buffer = DirectBuffer(
            address=self.address,
            size=self.size,
            view=self.view,
        )
        self._slice_cache[(0, self.size)] = self._primary_direct_buffer

    def get_or_create_slice_buffer(self, offset: int, block_size: int) -> DirectBuffer:
        """Retrieve pre-cached DirectBuffer slice or create and cache it (Zero allocation)."""
        key = (offset, block_size)
        buf = self._slice_cache.get(key)
        if buf is not None:
            return buf

        if offset + block_size > self.size:
            raise PayloadError(
                f"Requested slice [{offset}:{offset + block_size}] exceeds buffer size {self.size}"
            )

        block_view = self.view[offset : offset + block_size]
        buf = DirectBuffer(
            address=self.address + offset,
            size=block_size,
            view=block_view,
        )
        self._slice_cache[key] = buf
        return buf

    def apply_entropy(self, offset: int, block_size: int, seed: int) -> DirectBuffer:
        """Applies a deterministic seed-based entropy mask in-place using SIMD (Zero Allocation)."""
        buf = self.get_or_create_slice_buffer(offset, block_size)
        block_view = buf.view

        # Vectorized 64-bit SIMD in-place mutation using NumPy buffer view
        if len(block_view) >= 8:
            uint64_count = len(block_view) // 8
            np_arr = np.frombuffer(block_view[: uint64_count * 8], dtype=np.uint64)
            mask = np.uint64(seed ^ 0x5555555555555555)
            np_arr ^= mask

        return buf

    def mutate_entropy_block(
        self, offset: int, length: int, entropy_ratio: float = 0.8, seed: int = 42
    ) -> DirectBuffer:
        """Mutate a block with a given entropy ratio in-place (Zero Allocation)."""
        if not (0.0 <= entropy_ratio <= 1.0):
            raise InvalidEntropyError(
                f"Entropy ratio {entropy_ratio} must be between 0.0 and 1.0 inclusive"
            )

        buf = self.get_or_create_slice_buffer(offset, length)
        block_view = buf.view

        if len(block_view) >= 8:
            uint64_count = len(block_view) // 8
            np_arr = np.frombuffer(block_view[: uint64_count * 8], dtype=np.uint64)
            # Mutate proportional elements according to entropy_ratio
            mutate_elements = int(uint64_count * entropy_ratio)
            if mutate_elements > 0:
                mask = np.uint64(seed ^ 0x9E3779B97F4A7C15)
                np_arr[:mutate_elements] ^= mask

        return buf

    def mutate_direct_buffer(
        self, target: DirectBuffer, seed: int, entropy_ratio: float = 1.0
    ) -> None:
        """Direct in-place payload mutation on any DirectBuffer with 0 allocation."""
        view = target.view
        if len(view) >= 8:
            uint64_count = len(view) // 8
            np_arr = np.frombuffer(view[: uint64_count * 8], dtype=np.uint64)
            mutate_elements = int(uint64_count * min(max(entropy_ratio, 0.0), 1.0))
            if mutate_elements > 0:
                mask = np.uint64(seed ^ 0x9E3779B97F4A7C15)
                np_arr[:mutate_elements] ^= mask

    def close(self) -> None:
        """Release mmap resources and slice cache."""
        import contextlib

        for buf in list(self._slice_cache.values()):
            if hasattr(buf, "view"):
                with contextlib.suppress(Exception):
                    buf.view.release()
        self._slice_cache.clear()

        if hasattr(self, "view"):
            with contextlib.suppress(Exception):
                self.view.release()
            del self.view
        with contextlib.suppress(BufferError, OSError):
            self.buffer.close()
