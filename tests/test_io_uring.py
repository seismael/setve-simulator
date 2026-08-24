"""Comprehensive Unit Tests for IoUringTargetAdapter (Linux and Emulation paths)."""

from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from steve.adapters.base import (
    AdapterError,
    AlignmentError,
    DirectBuffer,
    HardwareIoError,
    QueueFullError,
    TargetDescriptor,
)
from steve.adapters.io_uring import IoUringTargetAdapter


@pytest.mark.asyncio
async def test_io_uring_alignment_verification() -> None:
    """Verify that 4096-byte alignment is enforced for address, size, and offset."""
    adapter = IoUringTargetAdapter()
    await adapter.initialize({})

    # 1. Misaligned address
    bad_addr_buf = DirectBuffer(address=4095, size=4096, view=memoryview(bytearray(4096)))
    desc = TargetDescriptor(endpoint_uri="file://local", resource_path="dummy.dat")

    with pytest.raises(AlignmentError, match="page boundary"):
        await adapter.write(desc, 0, bad_addr_buf)

    with pytest.raises(AlignmentError, match="page boundary"):
        await adapter.read(desc, 0, bad_addr_buf)

    # 2. Misaligned size
    bad_size_buf = DirectBuffer(address=4096, size=4000, view=memoryview(bytearray(4000)))
    with pytest.raises(AlignmentError, match="not a multiple of 4096 bytes"):
        await adapter.write(desc, 0, bad_size_buf)

    with pytest.raises(AlignmentError, match="not a multiple of 4096 bytes"):
        await adapter.read(desc, 0, bad_size_buf)

    # 3. Misaligned offset
    valid_buf = DirectBuffer(address=4096, size=4096, view=memoryview(bytearray(4096)))
    with pytest.raises(AlignmentError, match="File offset 1000 is not a multiple of 4096 bytes"):
        await adapter.write(desc, 1000, valid_buf)

    with pytest.raises(AlignmentError, match="File offset 1000 is not a multiple of 4096 bytes"):
        await adapter.read(desc, 1000, valid_buf)

    adapter.close()


@pytest.mark.asyncio
async def test_io_uring_lifecycle_fallback() -> None:
    """Test full write/read/flush/close lifecycle under POSIX fallback emulation."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_file = os.path.join(tmp_dir, "iouring_test.dat")
        desc = TargetDescriptor(endpoint_uri="file://local", resource_path=test_file)

        adapter = IoUringTargetAdapter(queue_depth=32)
        caps = adapter.capabilities()
        assert caps.supports_direct_io is True
        assert caps.supports_async_cancellation is True
        assert caps.max_concurrent_ops == 32
        assert caps.native_block_size == 4096

        write_data = bytearray(4096)
        write_data[:16] = b"IO_URING_DATA_01"
        write_buf = DirectBuffer(address=4096, size=4096, view=memoryview(write_data))

        written = await adapter.write(desc, 0, write_buf)
        assert written == 4096

        await adapter.flush(desc)

        read_data = bytearray(4096)
        read_buf = DirectBuffer(address=8192, size=4096, view=memoryview(read_data))
        read_bytes = await adapter.read(desc, 0, read_buf)
        assert read_bytes == 4096
        assert bytes(read_buf.view[:16]) == b"IO_URING_DATA_01"

        # Re-initialize idempotency
        await adapter.initialize({})

        adapter.close()
        # Verify fd map is empty after close
        assert len(adapter._fds) == 0


@pytest.mark.asyncio
async def test_io_uring_linux_mocked_paths() -> None:
    """Test Linux kernel io_uring submission, completion, and error branches via mocking."""
    mock_ring = MagicMock()
    mock_cqe = [MagicMock()]
    mock_sqe = MagicMock()

    adapter = IoUringTargetAdapter(queue_depth=64)
    adapter._ring = mock_ring
    adapter._cqe = mock_cqe

    with tempfile.TemporaryDirectory() as tmp_dir:
        test_file = os.path.join(tmp_dir, "mock_iouring.dat")
        desc = TargetDescriptor(endpoint_uri="file://local", resource_path=test_file)
        buf = DirectBuffer(address=4096, size=4096, view=memoryview(bytearray(4096)))

        try:
            with (
                patch("sys.platform", "linux"),
                patch("steve.adapters.io_uring.Ring", MagicMock(), create=True),
                patch("steve.adapters.io_uring.io_uring_queue_init", return_value=-1, create=True),
                pytest.raises(AdapterError, match="Failed to initialize io_uring ring"),
            ):
                await adapter.initialize({})

            with (
                patch("sys.platform", "linux"),
                patch("steve.adapters.io_uring.Ring", MagicMock(), create=True),
                patch("steve.adapters.io_uring.io_uring_queue_init", return_value=0, create=True),
                patch(
                    "steve.adapters.io_uring.io_uring_get_sqe",
                    return_value=None,
                    create=True,
                ),
                patch("steve.adapters.io_uring.io_uring_submit", return_value=0, create=True),
            ):
                adapter._initialized = False
                # Test QueueFullError on write
                with pytest.raises(QueueFullError, match="submission queue saturated"):
                    await adapter.write(desc, 0, buf)

                # Test QueueFullError on read
                with pytest.raises(QueueFullError, match="submission queue saturated"):
                    await adapter.read(desc, 0, buf)

            # Test HardwareIoError on negative CQE res
            mock_cqe[0].res = -5  # EIO
            with (
                patch("sys.platform", "linux"),
                patch("steve.adapters.io_uring.Ring", MagicMock(), create=True),
                patch(
                    "steve.adapters.io_uring.io_uring_get_sqe", return_value=mock_sqe, create=True
                ),
                patch("steve.adapters.io_uring.io_uring_prep_write", create=True),
                patch("steve.adapters.io_uring.io_uring_prep_read", create=True),
                patch("steve.adapters.io_uring.io_uring_submit", return_value=1, create=True),
                patch("steve.adapters.io_uring.io_uring_wait_cqe", create=True),
                patch("steve.adapters.io_uring.io_uring_cqe_seen", create=True),
            ):
                adapter._initialized = True
                with pytest.raises(HardwareIoError, match="Direct I/O write failed"):
                    await adapter.write(desc, 0, buf)

                with pytest.raises(HardwareIoError, match="Direct I/O read failed"):
                    await adapter.read(desc, 0, buf)

            # Test submit error (negative return from io_uring_submit)
            with (
                patch("sys.platform", "linux"),
                patch("steve.adapters.io_uring.Ring", MagicMock(), create=True),
                patch(
                    "steve.adapters.io_uring.io_uring_get_sqe", return_value=mock_sqe, create=True
                ),
                patch("steve.adapters.io_uring.io_uring_prep_write", create=True),
                patch("steve.adapters.io_uring.io_uring_prep_read", create=True),
                patch("steve.adapters.io_uring.io_uring_submit", return_value=-22, create=True),
            ):
                with pytest.raises(AdapterError, match="io_uring_submit failed"):
                    await adapter.write(desc, 0, buf)

                with pytest.raises(AdapterError, match="io_uring_submit failed"):
                    await adapter.read(desc, 0, buf)

            # Test happy path on Linux
            mock_cqe[0].res = 4096
            with (
                patch("sys.platform", "linux"),
                patch("steve.adapters.io_uring.Ring", MagicMock(), create=True),
                patch(
                    "steve.adapters.io_uring.io_uring_get_sqe", return_value=mock_sqe, create=True
                ),
                patch("steve.adapters.io_uring.io_uring_prep_write", create=True),
                patch("steve.adapters.io_uring.io_uring_prep_read", create=True),
                patch("steve.adapters.io_uring.io_uring_submit", return_value=1, create=True),
                patch("steve.adapters.io_uring.io_uring_wait_cqe", create=True),
                patch("steve.adapters.io_uring.io_uring_cqe_seen", create=True),
                patch("steve.adapters.io_uring.io_uring_queue_exit", create=True) as mock_exit,
            ):
                w = await adapter.write(desc, 0, buf)
                assert w == 4096
                r = await adapter.read(desc, 0, buf)
                assert r == 4096
                await adapter.flush(desc)
                adapter.close()
                mock_exit.assert_called_once_with(mock_ring)
        finally:
            adapter.close()
