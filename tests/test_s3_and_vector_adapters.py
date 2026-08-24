"""Unit tests for S3TargetAdapter and VectorTargetAdapter."""

import pytest

from steve.adapters.base import DirectBuffer, TargetDescriptor
from steve.adapters.s3 import S3TargetAdapter
from steve.adapters.vector import VectorTargetAdapter
from steve.exceptions import MisalignedBufferError


@pytest.mark.asyncio
async def test_s3_target_adapter_full_lifecycle() -> None:
    """Verify S3TargetAdapter initialization, write, read, flush, and capabilities."""
    adapter = S3TargetAdapter()
    await adapter.initialize({})

    caps = adapter.capabilities()
    assert caps.supports_direct_io is False
    assert caps.supports_async_cancellation is True
    assert caps.max_concurrent_ops == 512
    assert caps.native_block_size == 5242880  # 5MB

    desc = TargetDescriptor(endpoint_uri="s3://steve-bucket", resource_path="weights/model.bin")
    buf = DirectBuffer(address=4096, size=5242880, view=memoryview(bytearray(5242880)))

    written = await adapter.write(desc, 0, buf)
    assert written == 5242880

    read_bytes = await adapter.read(desc, 0, buf)
    assert read_bytes == 5242880

    await adapter.flush(desc)


@pytest.mark.asyncio
async def test_vector_target_adapter_full_lifecycle() -> None:
    """Verify VectorTargetAdapter initialization, 64B alignment, write, read, flush, caps."""
    adapter = VectorTargetAdapter()
    await adapter.initialize({})

    caps = adapter.capabilities()
    assert caps.supports_direct_io is False
    assert caps.supports_async_cancellation is True
    assert caps.max_concurrent_ops == 256
    assert caps.native_block_size == 64

    desc = TargetDescriptor(endpoint_uri="vector://qdrant", resource_path="collections/rag_docs")

    # 1. Valid 64-byte aligned buffer
    valid_buf = DirectBuffer(address=64, size=1536 * 4, view=memoryview(bytearray(1536 * 4)))
    written = await adapter.write(desc, 0, valid_buf)
    assert written == 1536 * 4

    read_bytes = await adapter.read(desc, 0, valid_buf)
    assert read_bytes == 1536 * 4

    await adapter.flush(desc)

    # 2. Misaligned buffer (address=63)
    bad_buf = DirectBuffer(address=63, size=128, view=memoryview(bytearray(128)))
    with pytest.raises(MisalignedBufferError, match="64-byte alignment"):
        await adapter.write(desc, 0, bad_buf)
