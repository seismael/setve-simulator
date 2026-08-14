"""Tests for PosixDirectIOAdapter Direct I/O operations."""

import tempfile
from pathlib import Path

import pytest

from setve.adapters.base import AlignmentError, DirectBuffer, TargetDescriptor
from setve.adapters.posix import PosixDirectIOAdapter


@pytest.mark.asyncio
async def test_posix_direct_io_write_and_read() -> None:
    """Verify PosixDirectIOAdapter accurately writes and reads data into DirectBuffer.view."""
    adapter = PosixDirectIOAdapter()
    await adapter.initialize({})

    with tempfile.TemporaryDirectory() as tmp_dir:
        test_file = Path(tmp_dir) / "posix_io_test.dat"
        desc = TargetDescriptor(endpoint_uri="posix://local", resource_path=str(test_file))

        block_size = 4096
        # Prepare write payload
        write_bytes = bytearray([0xAB] * block_size)
        write_buf = DirectBuffer(
            address=4096,
            size=block_size,
            view=memoryview(write_bytes),
        )

        # Write to file
        written = await adapter.write(desc, 0, write_buf)
        assert written == block_size

        await adapter.flush(desc)

        # Prepare read buffer (cleared)
        read_bytes = bytearray(block_size)
        read_buf = DirectBuffer(
            address=8192,
            size=block_size,
            view=memoryview(read_bytes),
        )

        # Read back from file
        bytes_read = await adapter.read(desc, 0, read_buf)
        assert bytes_read == block_size
        assert bytes(read_buf.view) == bytes(write_buf.view)

        adapter.close()


@pytest.mark.asyncio
async def test_posix_multi_target_management() -> None:
    """Verify PosixDirectIOAdapter correctly manages distinct file descriptors per target."""
    adapter = PosixDirectIOAdapter()
    await adapter.initialize({})

    with tempfile.TemporaryDirectory() as tmp_dir:
        target1 = TargetDescriptor(
            endpoint_uri="file://local", resource_path=str(Path(tmp_dir) / "target1.dat")
        )
        target2 = TargetDescriptor(
            endpoint_uri="file://local", resource_path=str(Path(tmp_dir) / "target2.dat")
        )

        block_size = 4096
        raw1 = bytearray(b"1" * block_size)
        raw2 = bytearray(b"2" * block_size)
        buf1 = DirectBuffer(address=4096, size=block_size, view=memoryview(raw1))
        buf2 = DirectBuffer(address=4096, size=block_size, view=memoryview(raw2))

        await adapter.write(target1, 0, buf1)
        await adapter.write(target2, 0, buf2)

        # Read back target 1
        read_raw = bytearray(block_size)
        read_buf = DirectBuffer(address=4096, size=block_size, view=memoryview(read_raw))
        await adapter.read(target1, 0, read_buf)
        assert bytes(read_buf.view) == bytes(b"1" * block_size)

        # Read back target 2
        await adapter.read(target2, 0, read_buf)
        assert bytes(read_buf.view) == bytes(b"2" * block_size)

        adapter.close()


@pytest.mark.asyncio
async def test_posix_misalignment_rejection() -> None:
    """Verify PosixDirectIOAdapter rejects unaligned buffers."""
    adapter = PosixDirectIOAdapter()
    desc = TargetDescriptor(endpoint_uri="file://local", resource_path="/tmp/unaligned.dat")

    # Address unaligned (4097)
    unaligned_buf = DirectBuffer(address=4097, size=4096, view=memoryview(bytearray(4096)))

    with pytest.raises(AlignmentError):
        await adapter.write(desc, 0, unaligned_buf)

    with pytest.raises(AlignmentError):
        await adapter.read(desc, 0, unaligned_buf)
