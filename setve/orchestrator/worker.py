"""Core-Pinned Worker Process Execution Engine."""

import asyncio
import time
from typing import Any

from setve.adapters.base import TargetAdapter, TargetDescriptor
from setve.orchestrator.affinity import pin_to_core
from setve.orchestrator.cluster import WorkerShardSpec
from setve.payload.mutator import PySIMDPayloadMutator
from setve.validation.metric_collector import MetricCollector
from setve.validation.reporter import WorkerTelemetryResult


class WorkerExecutionEngine:
    """Execution engine for core-pinned workers executing I/O workloads."""

    def __init__(
        self,
        shard_spec: WorkerShardSpec,
        target_uri: str,
        adapter_cls: type[TargetAdapter],
        duration_sec: int,
    ) -> None:
        self.shard_spec = shard_spec
        self.target_uri = target_uri
        self.adapter_cls = adapter_cls
        self.duration_sec = duration_sec
        self.collector = MetricCollector()

    async def execute(self) -> WorkerTelemetryResult:
        """Run the core-pinned event loop and return collected telemetry."""
        adapter = self.adapter_cls()
        await adapter.initialize({})

        mutator = PySIMDPayloadMutator(buffer_size=self.shard_spec.block_size_bytes)

        # Build descriptor logic based on URI
        resource_path = self.target_uri.replace("file://", "").replace("posix://", "")
        if not resource_path.startswith("/") and ":\\" not in resource_path:
            resource_path = f"./{resource_path}"
        descriptor = TargetDescriptor(
            endpoint_uri=self.target_uri,
            resource_path=f"{resource_path}_core_{self.shard_spec.core_id}.dat",
        )

        offset = self.shard_spec.base_offset_bytes
        stride = self.shard_spec.stride_bytes
        block_size = self.shard_spec.block_size_bytes

        queue_depth = adapter.capabilities().max_concurrent_ops
        keep_running = True

        async def _timer() -> None:
            nonlocal keep_running
            await asyncio.sleep(self.duration_sec)
            keep_running = False

        timer_task = asyncio.create_task(_timer())
        start_time = time.perf_counter()

        try:
            # Hot loop: Non-blocking core-pinned write execution with HDR telemetry
            while keep_running:
                for _ in range(queue_depth):
                    t0 = time.perf_counter_ns()
                    buf = mutator.apply_entropy(0, block_size, self.shard_spec.seed)
                    bytes_written = await adapter.write(descriptor, offset, buf)
                    elapsed_ns = time.perf_counter_ns() - t0

                    self.collector.record_latency(elapsed_ns)
                    self.collector.record_bytes(bytes_written)
                    offset += stride

                # Yield control to event loop to allow timer check and async task processing
                await asyncio.sleep(0)
        finally:
            timer_task.cancel()
            buf = None  # Release reference to direct buffer view
            mutator.close()
            await adapter.flush(descriptor)
            if hasattr(adapter, "close"):
                adapter.close()


        actual_duration = max(time.perf_counter() - start_time, 1e-6)

        return WorkerTelemetryResult(
            core_id=self.shard_spec.core_id,
            node_id=self.shard_spec.node_id,
            total_ops=self.collector.total_ops,
            total_bytes=self.collector.total_bytes,
            duration_sec=actual_duration,
            p50_ms=self.collector.p50_latency_ms(),
            p90_ms=self.collector.p90_latency_ms(),
            p99_ms=self.collector.p99_latency_ms(),
            p999_ms=self.collector.p999_latency_ms(),
            throughput_gbps=self.collector.throughput_gbps(actual_duration),
        )


def run_worker_process(
    shard_spec: WorkerShardSpec,
    target_uri: str,
    adapter_cls: type[TargetAdapter],
    duration_sec: int,
    telemetry_queue: Any = None,
) -> None:
    """Multiprocessing entrypoint: Pinned to a single core, running an isolated event loop."""
    pin_to_core(shard_spec.core_id)

    try:
        import uvloop  # type: ignore[import-not-found, unused-ignore]

        uvloop.install()
    except ImportError:
        pass

    engine = WorkerExecutionEngine(shard_spec, target_uri, adapter_cls, duration_sec)
    result = asyncio.run(engine.execute())

    if telemetry_queue is not None:
        telemetry_queue.put(result)
