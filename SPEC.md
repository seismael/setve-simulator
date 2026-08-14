# SPEC.md: Universal Simulation & Telemetry Validation Engine (SETVE) Technical Specification

## 1. System Vision & Architecture Topology

The **Universal Simulation & Telemetry Validation Engine (SETVE)** is a high-throughput, platform-agnostic load generation and out-of-band telemetry verification framework designed to stress-test high-performance storage and data-plane systems (saturating $\ge 8\text{ GB/s}$ per node up to multi-TB/s clusters).

```
                       ┌───────────────────────────────┐
                       │  Orchestration Master Engine  │
                       │     (Control & Workflow)      │
                       └───────────────┬───────────────┘
                                       │
                ┌──────────────────────┴──────────────────────┐
                │ Spawns & Controls (1 Worker / Physical Core)│
                ▼                                             ▼
┌──────────────────────────────┐              ┌──────────────────────────────┐
│       Worker Process 0       │              │       Worker Process N       │
│ ┌──────────────────────────┐ │              │ ┌──────────────────────────┐ │
│ │ uvloop Event Loop        │ │              │ │ uvloop Event Loop        │ │
│ ├──────────────────────────┤ │   . . . . .  │ ├──────────────────────────┤ │
│ │ PySIMDPayloadMutator     │ │              │ │ PySIMDPayloadMutator     │ │
│ ├──────────────────────────┤ │              │ ├──────────────────────────┤ │
│ │ TargetAdapter (io_uring) │ │              │ │ TargetAdapter (io_uring) │ │
│ └─────────────┬────────────┘ │              │ └─────────────┬────────────┘ │
└───────────────┼──────────────┘              └───────────────┼──────────────┘
                │ Direct I/O                                  │ Direct I/O
                └──────────────────────┬──────────────────────┘
                                       ▼
                       ┌───────────────────────────────┐
                       │   SYSTEM UNDER TEST (SUT)     │
                       └───────────────┬───────────────┘
                                       │ Out-of-Band Observability
                                       ▼
                       ┌───────────────────────────────┐
                       │ eBPF / ClickHouse             │
                       │ Triangulation Engine          │
                       └───────────────────────────────┘
```

---

## 2. Subsystem Functional Specifications

### 2.1 Orchestration Subsystem (`setve/orchestrator/`)
- **`master.py` (`MultiCoreOrchestrator`):** Process lifecycle manager. Spawns per-core workers, distributes target descriptors, monitors child process health, and coordinates graceful teardown via signal handling.
- **`worker.py` (`_worker_process_main`):** Core-pinned worker process entrypoint. Installs `uvloop`, initializes target adapters, and executes non-blocking load generation loops.
- **`affinity.py`:** Hardware topology inspector mapping NUMA domains and physical cores (`os.sched_setaffinity`) to eliminate thread migration overhead.

### 2.2 Payload Subsystem (`setve/payload/`)
- **`mutator.py` (`PySIMDPayloadMutator`):** In-place C/NumPy SIMD mutation engine altering payload entropy ($\alpha \in [0.0, 1.0]$) at line rate without re-allocation.
- **`buffer_pool.py` (`BufferPool`):** Page-aligned anonymous `mmap` ring buffer allocator providing zero-copy `memoryview` slices to worker tasks.
- **`profiles.py`:** Workload profile definitions (e.g., AI LLM prefill/decode sequences, high-rate video streams, small-block POSIX I/O).

### 2.3 Target Adapters Subsystem (`setve/adapters/`)
- **`base.py` (`TargetAdapter`, `DirectBuffer`, `TargetDescriptor`):** Standard abstract base class defining `read()`, `write()`, and `flush()` interfaces over aligned `DirectBuffer` objects.
- **`posix.py` (`PosixDirectIOAdapter`):** Direct I/O (`O_DIRECT`) filesystem target driver enforcing sector alignment.
- **`io_uring.py` (`IoUringTargetAdapter`):** Linux kernel-bypass driver using `liburing`. Prepares Submission Queue Entries (SQEs) and reaps Completion Queue Events (CQEs) without per-op system calls.
- **`s3.py` (`S3TargetAdapter`):** Async HTTP multipart S3 object store adapter.
- **`vector.py` (`VectorTargetAdapter`):** Embedding and vector database gRPC/REST API driver.

### 2.4 Telemetry & Validation Subsystem (`setve/validation/`)
- **`ebpf_probe.py`:** Native Linux eBPF/XDP kernel tracepoints capturing physical NIC and block layer I/O counters out-of-band.
- **`metric_collector.py`:** Sub-millisecond HDRHistogram latency and throughput aggregation.
- **`evaluator.py`:** Telemetry divergence engine calculating metric skew ($\Delta \text{telemetry}$) between SUT self-reported stats and eBPF ground truth.

---

## 3. Core Technical Constraints

1. **Zero-Allocation Hot Path:** Zero dynamic heap object instantiations within active I/O or mutation loops. Pre-allocated `mmap` buffers sliced via `memoryview`.
2. **Physical Core Isolation:** 1 worker process per physical CPU core using `os.sched_setaffinity`. Independent `uvloop` event loops and `io_uring` instances per core.
3. **Hardware Alignment:** Rigid enforcement of $4096\text{-byte}$ alignment for storage buffers and $64\text{-byte}$ alignment for AVX-512 SIMD vectors.
4. **Interface Decoupling:** Core engines interact strictly through `TargetAdapter` ABCs.

---

## 4. Implementation Reference Blueprints

### 4.1 Multi-Core Core-Pinned Worker Blueprint

```python
import asyncio
import multiprocessing as mp
import os
from typing import List
import uvloop

from setve.adapters.posix import PosixDirectIOAdapter
from setve.adapters.base import TargetDescriptor
from setve.payload.mutator import PySIMDPayloadMutator


def _worker_process_main(
    core_id: int, 
    resource_path: str, 
    block_size: int, 
    entropy_ratio: float, 
    duration_sec: int
) -> None:
    """Worker entrypoint: Pinned to a single core, running an isolated uvloop event loop."""
    os.sched_setaffinity(0, {core_id})
    uvloop.install()

    async def _run_workload():
        adapter = PosixDirectIOAdapter()
        await adapter.initialize({})

        mutator = PySIMDPayloadMutator(buffer_size=block_size * 16)
        descriptor = TargetDescriptor(
            endpoint_uri="file://local",
            resource_path=f"{resource_path}_core_{core_id}.dat"
        )

        offset = 0
        end_time = asyncio.get_running_loop().time() + duration_sec
        ops_completed = 0

        try:
            while asyncio.get_running_loop().time() < end_time:
                direct_buf = mutator.mutate_entropy_block(
                    offset=0, 
                    length=block_size, 
                    entropy_ratio=entropy_ratio
                )
                await adapter.write(descriptor, offset, direct_buf)
                offset += block_size
                ops_completed += 1

            print(f"[Core {core_id}] Completed {ops_completed} ops ({ops_completed * block_size / 1e9:.2f} GB)")
        finally:
            mutator.close()

    asyncio.run(_run_workload())


class MultiCoreOrchestrator:
    """Master controller that spawns and manages core-pinned simulation workers."""

    def __init__(self, core_ids: List[int]):
        self.core_ids = core_ids
        self.processes: List[mp.Process] = []

    def start(self, resource_prefix: str, block_size: int = 1048576, entropy: float = 0.8, duration: int = 10):
        print(f"Spawning {len(self.core_ids)} worker processes across cores {self.core_ids}...")
        
        for core_id in self.core_ids:
            p = mp.Process(
                target=_worker_process_main,
                args=(core_id, resource_prefix, block_size, entropy, duration),
                daemon=True
            )
            p.start()
            self.processes.append(p)

        for p in self.processes:
            p.join()

        print("All simulation workers completed successfully.")
```

### 4.2 Linux `io_uring` Zero-Copy Adapter Blueprint

```python
import os
from typing import Dict, Any
from liburing import (
    Ring, Cqe, io_uring_queue_init, io_uring_queue_exit,
    io_uring_get_sqe, io_uring_prep_write, io_uring_submit,
    io_uring_wait_cqe, io_uring_cqe_seen, O_DIRECT, O_WRONLY, O_CREAT
)

from setve.adapters.base import TargetAdapter, TargetDescriptor, DirectBuffer, AdapterCapabilities


class IoUringTargetAdapter(TargetAdapter):
    """Zero-copy target adapter leveraging Linux io_uring kernel-bypass queues."""

    def __init__(self, queue_depth: int = 1024):
        self.queue_depth = queue_depth
        self.ring = Ring()
        self.cqe = Cqe()
        self._capabilities = AdapterCapabilities(
            supports_direct_io=True,
            supports_async_cancellation=True,
            max_concurrent_ops=queue_depth,
            native_block_size=4096,
        )

    async def initialize(self, config: Dict[str, Any]) -> None:
        res = io_uring_queue_init(self.queue_depth, self.ring, 0)
        if res < 0:
            raise OSError(-res, "Failed to initialize io_uring queue")

    async def write(self, target: TargetDescriptor, offset: int, payload: DirectBuffer) -> int:
        flags = O_WRONLY | O_CREAT | O_DIRECT
        fd = os.open(target.resource_path, flags, 0o666)
        
        try:
            sqe = io_uring_get_sqe(self.ring)
            if not sqe:
                io_uring_submit(self.ring)
                sqe = io_uring_get_sqe(self.ring)

            io_uring_prep_write(sqe, fd, payload.view, offset)
            sqe.user_data = 1

            io_uring_submit(self.ring)

            io_uring_wait_cqe(self.ring, self.cqe)
            cqe_entry = self.cqe[0]
            result = cqe_entry.res

            if result < 0:
                raise OSError(-result, "io_uring write operation failed")

            io_uring_cqe_seen(self.ring, cqe_entry)
            return result
        finally:
            os.close(fd)

    async def read(self, target: TargetDescriptor, offset: int, buffer: DirectBuffer) -> int:
        raise NotImplementedError("Read implementation follows identical SQE/CQE prep pattern.")

    async def flush(self, target: TargetDescriptor) -> None:
        pass

    def capabilities(self) -> AdapterCapabilities:
        return self._capabilities

    def close(self):
        io_uring_queue_exit(self.ring)
```

---

## 7. Production Use Cases & Execution Catalog

Production-ready use case scenarios are maintained in the [`usecases/`](file:///c:/dev/projects/setve-simulator/usecases) package:

1. **`usecases/usecase_01_storage_stress.py`**: Zero-copy POSIX Direct I/O (`O_DIRECT`) multi-core storage saturation.
2. **`usecases/usecase_02_dedup_compression.py`**: In-place AVX-512 SIMD entropy sweeps for deduplication and compression validation.
3. **`usecases/usecase_03_prometheus_monitoring.py`**: Real-time telemetry extraction, HDR percentiles ($p_{50}, p_{90}, p_{99}$), and Prometheus text exposition.
4. **`usecases/usecase_04_ebpf_triangulation.py`**: Out-of-band kernel/hardware trace counter triangulation ($\le 0.1\%$ SLA).
5. **`usecases/usecase_05_ai_vector_s3.py`**: High-density AI embedding batch upserts & multipart S3 object streaming.
6. **`usecases/usecase_06_ai_kv_cache_checkpointing.py`**: AI LLM prefill context burst, random KV-cache decode, and weight checkpoints.
7. **`usecases/usecase_07_multitenant_qos_noisy_neighbor.py`**: Multi-tenant QoS contention and mission-critical tail-latency SLA audit.
8. **`usecases/usecase_08_chaos_node_failure.py`**: Distributed generator chaos engineering, node failure, and dynamic shard rebalancing.
9. **`usecases/usecase_09_storage_tiering_lifecycle.py`**: Automated data tiering across Hot NVMe $\rightarrow$ Warm Block $\rightarrow$ Cold S3.
10. **`usecases/usecase_10_tail_latency_microburst.py`**: High-resolution 64-bucket HDR histogram analysis under $50\text{ ms}$ micro-bursts.


