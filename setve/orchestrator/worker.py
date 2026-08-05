"""Core-Pinned Worker Process Execution Engine."""

import asyncio
from typing import Type

from setve.adapters.base import TargetAdapter, TargetDescriptor
from setve.orchestrator.affinity import pin_to_core
from setve.orchestrator.cluster import WorkerShardSpec
from setve.payload.mutator import PySIMDPayloadMutator


class WorkerExecutionEngine:
    """Execution engine for core-pinned workers executing I/O workloads."""

    def __init__(
        self,
        shard_spec: WorkerShardSpec,
        target_uri: str,
        adapter_cls: Type[TargetAdapter],
        duration_sec: int,
    ) -> None:
        self.shard_spec = shard_spec
        self.target_uri = target_uri
        self.adapter_cls = adapter_cls
        self.duration_sec = duration_sec

    async def execute(self) -> None:
        """Run the core-pinned event loop."""
        adapter = self.adapter_cls()
        await adapter.initialize({})

        mutator = PySIMDPayloadMutator(buffer_size=self.shard_spec.block_size_bytes)
        
        # Build descriptor logic based on URI - for simplicity assuming posix files
        resource_path = self.target_uri.replace("file://", "").replace("posix://", "")
        if not resource_path.startswith("/"):
            resource_path = f"./{resource_path}"
        descriptor = TargetDescriptor(
            endpoint_uri=self.target_uri,
            resource_path=f"{resource_path}_core_{self.shard_spec.core_id}.dat",
        )

        offset = self.shard_spec.base_offset_bytes
        stride = self.shard_spec.stride_bytes
        block_size = self.shard_spec.block_size_bytes
        ops = 0
        
        queue_depth = adapter.capabilities().max_concurrent_ops
        keep_running = True

        async def _timer() -> None:
            nonlocal keep_running
            await asyncio.sleep(self.duration_sec)
            keep_running = False

        timer_task = asyncio.create_task(_timer())

        try:
            # Hot loop: Zero GIL overhead per block, maximizing asynchronous queue depth
            while keep_running:
                tasks = []
                for _ in range(queue_depth):
                    buf = mutator.apply_entropy(0, block_size, self.shard_spec.seed)
                    tasks.append(adapter.write(descriptor, offset, buf))
                    offset += stride  # Stride across offset space
                    ops += 1
                
                # Await entire queue batch
                await asyncio.gather(*tasks)
        finally:
            timer_task.cancel()
            mutator.close()
            await adapter.flush(descriptor)
            if hasattr(adapter, "close"):
                adapter.close()


def run_worker_process(
    shard_spec: WorkerShardSpec,
    target_uri: str,
    adapter_cls: Type[TargetAdapter],
    duration_sec: int,
) -> None:
    """Multiprocessing entrypoint: Pinned to a single core, running an isolated event loop."""
    pin_to_core(shard_spec.core_id)

    try:
        import uvloop  # type: ignore[import-not-found, unused-ignore]
        uvloop.install()
    except ImportError:
        pass

    engine = WorkerExecutionEngine(shard_spec, target_uri, adapter_cls, duration_sec)
    asyncio.run(engine.execute())
