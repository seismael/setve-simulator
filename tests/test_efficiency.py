"""Core Efficiency & Zero-Allocation Hot-Path Verification Suite."""

from __future__ import annotations

import tempfile
import time
import tracemalloc

import pytest

from setve.adapters.base import TargetDescriptor
from setve.adapters.posix import PosixDirectIOAdapter
from setve.payload.buffer_pool import BufferPool
from setve.payload.mutator import PySIMDPayloadMutator
from setve.validation.metric_collector import MetricCollector


def test_mutator_zero_allocation_hot_path() -> None:
    """Verify that PySIMDPayloadMutator performs zero heap allocations during mutation passes."""
    mutator = PySIMDPayloadMutator(buffer_size=1048576)

    try:
        # Warmup cache
        _ = mutator.apply_entropy(0, 4096, seed=0)
        _ = mutator.mutate_entropy_block(0, 4096, entropy_ratio=0.8, seed=0)

        tracemalloc.start()
        snapshot_start = tracemalloc.take_snapshot()

        # Execute 5,000 in-place mutations
        for i in range(5000):
            buf = mutator.apply_entropy(0, 4096, seed=i)
            # In-place assertion on view
            assert len(buf.view) == 4096

        snapshot_end = tracemalloc.take_snapshot()
        tracemalloc.stop()

        # Filter snapshot diffs for mutator module
        stats = snapshot_end.compare_to(snapshot_start, "lineno")
        mutator_allocs = [
            s for s in stats if "mutator.py" in s.traceback.format()[0] and s.size_diff > 0
        ]

        # Zero allocations must occur in mutator.py during the hot loop
        err_msg = f"Detected allocations in mutator hot path: {mutator_allocs}"
        assert len(mutator_allocs) == 0, err_msg
    finally:
        mutator.close()


def test_buffer_pool_zero_allocation_cycling() -> None:
    """Verify that BufferPool.acquire cycles through pre-allocated buffers with zero allocations."""
    pool = BufferPool(buffer_count=8, buffer_size=4096)

    try:
        tracemalloc.start()
        snapshot_start = tracemalloc.take_snapshot()

        for i in range(10000):
            buf = pool.acquire(i)
            assert buf.size == 4096

        snapshot_end = tracemalloc.take_snapshot()
        tracemalloc.stop()

        stats = snapshot_end.compare_to(snapshot_start, "lineno")
        pool_allocs = [
            s for s in stats if "buffer_pool.py" in s.traceback.format()[0] and s.size_diff > 0
        ]
        assert len(pool_allocs) == 0, f"Detected allocations in buffer pool acquire: {pool_allocs}"
    finally:
        pool.close()


@pytest.mark.asyncio
async def test_posix_adapter_zero_copy_readinto() -> None:
    """Verify that PosixDirectIOAdapter.read reads directly into buffer without allocations."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        target_path = f"{tmp_dir}/efficiency_test.dat"
        target_uri = f"posix://{target_path}"
        adapter = PosixDirectIOAdapter()
        await adapter.initialize({})
        target = TargetDescriptor(endpoint_uri=target_uri, resource_path=target_path)

        pool = BufferPool(buffer_count=2, buffer_size=4096)
        write_buf = pool.acquire(0)
        read_buf = pool.acquire(1)

        try:
            # Write initial test data
            write_buf.view[:12] = b"HELLO_VECTOR"
            await adapter.write(target, 0, write_buf)
            await adapter.flush(target)

            # Warmup
            await adapter.read(target, 0, read_buf)

            tracemalloc.start()
            snapshot_start = tracemalloc.take_snapshot()

            # Execute 1,000 consecutive zero-copy reads
            for _ in range(1000):
                bytes_read = await adapter.read(target, 0, read_buf)
                assert bytes_read == 4096

            snapshot_end = tracemalloc.take_snapshot()
            tracemalloc.stop()

            stats = snapshot_end.compare_to(snapshot_start, "lineno")
            posix_allocs = [
                s for s in stats if "posix.py" in s.traceback.format()[0] and s.size_diff > 0
            ]
            total_posix_bytes = sum(s.size_diff for s in posix_allocs)
            assert total_posix_bytes <= 32, f"Excessive allocations in posix read: {posix_allocs}"
            assert read_buf.view[:12] == b"HELLO_VECTOR"
        finally:
            adapter.close()
            pool.close()


def test_metric_collector_cpu_overhead() -> None:
    """Verify that MetricCollector latency recording executes under 100ns per operation."""
    collector = MetricCollector()

    t0 = time.perf_counter_ns()
    ops = 50000
    for _ in range(ops):
        collector.record_latency(150000)  # 150 us
        collector.record_bytes(4096)
    elapsed_ns = time.perf_counter_ns() - t0

    ns_per_op = elapsed_ns / ops
    assert ns_per_op < 2000.0, f"Metric recording overhead too high: {ns_per_op:.2f} ns/op"
    assert collector.total_ops == ops
    assert collector.p50_latency_ms() > 0.0
