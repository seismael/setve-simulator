"""Tests for BufferPool page-aligned mmap ring allocator."""

from setve.payload.buffer_pool import BufferPool


def test_buffer_pool_allocation_and_alignment() -> None:
    """Verify BufferPool allocates specified count of page-aligned DirectBuffer instances."""
    pool = BufferPool(buffer_count=4, buffer_size=4096)
    try:
        assert len(pool._buffers) == 4
        for buf in pool._buffers:
            assert buf.size == 4096
            buf.assert_alignment(4096)
            buf.assert_alignment(64)
    finally:
        pool.close()


def test_buffer_pool_acquire_cycling() -> None:
    """Verify acquire cycles deterministically across the ring buffer pool."""
    pool = BufferPool(buffer_count=3, buffer_size=4096)
    try:
        buf0 = pool.acquire(0)
        buf1 = pool.acquire(1)
        buf2 = pool.acquire(2)
        buf3 = pool.acquire(3)

        assert buf0.address == pool._buffers[0].address
        assert buf1.address == pool._buffers[1].address
        assert buf2.address == pool._buffers[2].address
        assert buf3.address == buf0.address
    finally:
        pool.close()
