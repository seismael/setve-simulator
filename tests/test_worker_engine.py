"""Comprehensive Unit Tests for WorkerExecutionEngine and Worker Process Bootstrap."""

from __future__ import annotations

import multiprocessing as mp
import tempfile

import pytest

from steve.adapters.base import AdapterCapabilities, DirectBuffer, TargetAdapter, TargetDescriptor
from steve.orchestrator.cluster import WorkerShardSpec
from steve.orchestrator.worker import WorkerExecutionEngine, run_worker_process


class MockFailingAdapter(TargetAdapter):
    """Adapter that fails during write for error propagation verification."""

    def __init__(self) -> None:
        self._caps = AdapterCapabilities(
            supports_direct_io=True,
            supports_async_cancellation=False,
            max_concurrent_ops=4,
            native_block_size=4096,
        )

    async def initialize(self, config: dict[str, object]) -> None:
        pass

    async def write(self, target: TargetDescriptor, offset: int, payload: DirectBuffer) -> int:
        raise OSError("Injected simulated I/O disk failure")

    async def read(self, target: TargetDescriptor, offset: int, buffer: DirectBuffer) -> int:
        return 0

    async def flush(self, target: TargetDescriptor) -> None:
        raise OSError("Injected flush failure")

    def capabilities(self) -> AdapterCapabilities:
        return self._caps

    def close(self) -> None:
        pass


@pytest.mark.asyncio
async def test_worker_execution_engine_success() -> None:
    """Verify that WorkerExecutionEngine runs, measures telemetry, and shuts down cleanly."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        target_path = f"{tmp_dir}/worker_test.dat"
        spec = WorkerShardSpec(
            node_id="test-node-01",
            core_id=0,
            base_offset_bytes=0,
            stride_bytes=4096,
            block_size_bytes=4096,
            seed=42,
            target_throughput_bps=1024 * 1024 * 1024,
        )

        from steve.adapters.posix import PosixDirectIOAdapter

        engine = WorkerExecutionEngine(
            shard_spec=spec,
            target_uri=f"posix://{target_path}",
            adapter_cls=PosixDirectIOAdapter,
            duration_sec=0.2,
        )

        res = await engine.execute()
        assert res.core_id == 0
        assert res.node_id == "test-node-01"
        assert res.total_ops > 0
        assert res.total_bytes > 0
        assert res.duration_sec > 0
        assert res.throughput_gbps > 0
        assert res.error_message is None


@pytest.mark.asyncio
async def test_worker_execution_engine_error_capture() -> None:
    """Verify that exceptions during worker hot loop are captured into telemetry error_message."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        target_path = f"{tmp_dir}/fail_worker.dat"
        spec = WorkerShardSpec(
            node_id="fail-node-01",
            core_id=1,
            base_offset_bytes=0,
            stride_bytes=4096,
            block_size_bytes=4096,
            seed=42,
            target_throughput_bps=1024 * 1024 * 1024,
        )

        engine = WorkerExecutionEngine(
            shard_spec=spec,
            target_uri=f"posix://{target_path}",
            adapter_cls=MockFailingAdapter,
            duration_sec=0.1,
        )

        res = await engine.execute()
        assert res.core_id == 1
        assert res.error_message is not None
        assert "Injected simulated I/O disk failure" in res.error_message


def test_run_worker_process_queue_dispatch() -> None:
    """Verify run_worker_process execution and queue result delivery."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        target_path = f"{tmp_dir}/proc_worker.dat"
        spec = WorkerShardSpec(
            node_id="proc-node-01",
            core_id=0,
            base_offset_bytes=0,
            stride_bytes=4096,
            block_size_bytes=4096,
            seed=101,
            target_throughput_bps=512 * 1024 * 1024,
        )

        from steve.adapters.posix import PosixDirectIOAdapter
        from steve.validation.reporter import WorkerTelemetryResult

        q: mp.Queue[WorkerTelemetryResult] = mp.Queue()
        run_worker_process(
            shard_spec=spec,
            target_uri=f"posix://{target_path}",
            adapter_cls=PosixDirectIOAdapter,
            duration_sec=0.1,
            telemetry_queue=q,
        )

        res = q.get(timeout=2.0)
        assert res.core_id == 0
        assert res.node_id == "proc-node-01"
        assert res.total_ops > 0
        assert res.error_message is None
