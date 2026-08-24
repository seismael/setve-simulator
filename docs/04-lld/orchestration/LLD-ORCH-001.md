---
id: "LLD-ORCH-001"
title: "Master Orchestrator Process Manager & gRPC Synchronization Engine"
type: "LLD"
status: "APPROVED"
domain: "control-plane"
layer: "compute-engine"
c4_level: "code"
diataxis_type: "reference"
traceability:
  implements_brd: ["BRD-STEVE-001", "BRD-DIST-001"]
  governed_by_adr: ["ADR-0001", "ADR-0002"]
  parent_hld: "HLD-DIST-001"
  child_llds: []
code_references:
  - "steve/orchestrator/master.py"
  - "steve/orchestrator/worker.py"
  - "steve/orchestrator/cluster.py"
  - "steve/orchestrator/sync.py"
  - "steve/orchestrator/affinity.py"
  - "steve/validation/metric_collector.py"
  - "steve/validation/reporter.py"
test_references:
  - "tests/test_cluster_sync.py"
  - "tests/test_sharding.py"
  - "tests/test_master_telemetry.py"
  - "tests/test_reporter.py"
owner: "@architecture-team"
last_validated_date: "2026-08-05"
---


# LLD-ORCH-001: Master Orchestrator Process Manager & gRPC Synchronization Engine

## 1. Module Overview & Class Structure

`LLD-ORCH-001` provides the low-level technical specification for `MasterOrchestrator` and `ClusterOrchestratorServicer`. The module manages master control-plane state, distributes deterministic workload shards, and executes the two-phase gRPC barrier release sequence across registered cluster nodes.

```text
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 DISTRIBUTED HORIZONTAL TOPOLOGY                                 │
├─────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                 │
│                           ┌──────────────────────────────────────────┐                          │
│                           │      STEVE Master Orchestrator Node      │                          │
│                           │   (Deterministic Sharding + gRPC Sync)   │                          │
│                           └──────┬────────────────────────────┬──────┘                          │
│                                  │ Phase 1 & 2 gRPC Barriers  │                                 │
│                   ┌──────────────┴──────────────┐             └──────────────┐                  │
│                   ▼                             ▼                            ▼                  │
│   ┌───────────────────────────────┐ ┌───────────────────────────────┐ ┌──────────────────────┐  │
│   │    Physical Node 01 (K8s)     │ │    Physical Node 02 (K8s)     │ │ Physical Node N (K8s)│  │
│   │ ┌───────────────────────────┐ │ │ ┌───────────────────────────┐ │ │ ┌──────────────────┐ │  │
│   │ │ Core 0 Worker (uvloop)    │ │ │ │ Core 0 Worker (uvloop)    │ │ │ │ Core 0 Worker    │ │  │
│   │ ├───────────────────────────┤ │ │ ├───────────────────────────┤ │ │ ├──────────────────┤ │  │
│   │ │ Core 1 Worker (uvloop)    │ │ │ │ Core 1 Worker (uvloop)    │ │ │ │ Core 1 Worker    │ │  │
│   │ └─────────────┬─────────────┘ │ │ └─────────────┬─────────────┘ │ │ └────────┬─────────┘ │  │
│   └───────────────┼───────────────┘ └───────────────┼───────────────┘ └──────────┼───────────┘  │
│                   │                                 │                            │              │
│                   │ Non-Overlapping Direct I/O      │ Non-Overlapping Direct I/O │              │
│                   ▼                                 ▼                            ▼              │
│   ┌──────────────────────────────────────────────────────────────────────────────────────────┐  │
│   │                           DISTRIBUTED STORAGE SYSTEM UNDER TEST                          │  │
│   │               (Shared NVMe-oF Fabric / Ceph / AWS S3 / Milvus Vector DB)                 │  │
│   └──────────────────────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 1.1 Vertical vs. Horizontal Scaling Matrix

| Dimension | Vertical Scaling (Intra-Node) | Horizontal Scaling (Inter-Node) |
| :--- | :--- | :--- |
| **Mechanism** | `multiprocessing` + `sched_setaffinity` | gRPC barrier sync + Kubernetes DaemonSet |
| **Concurrency** | 1 isolated process per physical CPU core | 1 to 64+ physical servers |
| **Memory Model** | Page-aligned `mmap` ring buffers ($4096\text{B}$) | Independent physical RAM per server (Shared-Nothing) |
| **Data Hot Path** | Zero-allocation `memoryview` + AVX-512 XOR | Zero inter-node network traffic during I/O |
| **Target Scale** | $\ge 8\text{ GB/s}$ ($64\text{ Gbps}$) per server node | $\ge 1\text{ TB/s}$ ($8\text{ Tbps}$) cluster aggregate |

---

## 2. Deterministic Hash Generator Implementation

To ensure that distributed nodes compute non-overlapping offset spaces and entropy seeds without exchanging locks during execution passes, the master generates seeds via a 64-bit SplitMix algorithm.

```python
"""Deterministic seed and offset partition generator for distributed cluster execution."""

from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass(frozen=True, slots=True)
class WorkerShardSpec:
    node_id: str
    core_id: int
    seed: int
    base_offset_bytes: int
    stride_bytes: int
    target_throughput_bps: int


class DeterministicShardGenerator:
    """Calculates non-overlapping payload seeds and block offsets per core worker."""

    @staticmethod
    def _splitmix64(state: int) -> int:
        """64-bit deterministic SplitMix hash function."""
        z = (state + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF
        return (z ^ (z >> 31)) & 0xFFFFFFFFFFFFFFFF

    @classmethod
    def generate_cluster_shards(
        self,
        global_seed: int,
        nodes: List[Tuple[str, int]],  # List of (node_id, core_count)
        target_total_throughput_bps: int,
        block_size: int = 1048576,
    ) -> Dict[str, List[WorkerShardSpec]]:
        """Generates deterministic worker shard configurations across all physical nodes."""
        total_cores = sum(cores for _, cores in nodes)
        per_core_throughput = target_total_throughput_bps // total_cores

        shards: Dict[str, List[WorkerShardSpec]] = {}
        global_core_index = 0

        for node_id, core_count in nodes:
            node_shards: List[WorkerShardSpec] = []
            for local_core in range(core_count):
                # Hash global seed combined with global core ordinal
                combined_state = (global_seed ^ global_core_index) & 0xFFFFFFFFFFFFFFFF
                worker_seed = self._splitmix64(combined_state)

                # Calculate strided byte offset
                base_offset = global_core_index * block_size
                stride = total_cores * block_size

                spec = WorkerShardSpec(
                    node_id=node_id,
                    core_id=local_core,
                    seed=worker_seed,
                    base_offset_bytes=base_offset,
                    stride_bytes=stride,
                    target_throughput_bps=per_core_throughput,
                )
                node_shards.append(spec)
                global_core_index += 1

            shards[node_id] = node_shards

        return shards
```

---

## 3. Barrier Synchronization Servicer (`steve/orchestrator/sync.py`)

```python
"""gRPC Servicer enforcing two-phase cluster barrier synchronization."""

import asyncio
import time
from typing import Dict, Any
from steve.orchestrator.sync_pb2 import (
    BlueprintRequest,
    BlueprintResponse,
    ReadySignal,
    WaitResponse,
)
from steve.orchestrator.sync_pb2_grpc import ClusterOrchestratorServicer


class ClusterSyncServicer(ClusterOrchestratorServicer):
    """gRPC servicer handling node barrier readiness and synchronized release."""

    def __init__(self, expected_node_count: int, sync_lead_time_ms: int = 500):
        self._expected_node_count: int = expected_node_count
        self._sync_lead_time_ms: int = sync_lead_time_ms
        self._ready_nodes: Dict[str, ReadySignal] = {}
        self._release_event: asyncio.Event = asyncio.Event()
        self._synchronized_start_us: int = 0

    async def SignalReady(self, request: ReadySignal, context: Any) -> WaitResponse:
        """Invoked by node daemons when local ring buffers and io_uring queues are ready."""
        self._ready_nodes[request.node_id] = request

        # If all nodes report PREPARED, release barrier with future epoch timestamp
        if len(self._ready_nodes) >= self._expected_node_count:
            # Set synchronized start 500ms in the future to absorb network latency
            future_epoch_us = int((time.time() * 1_000_000) + (self._sync_lead_time_ms * 1_000))
            self._synchronized_start_us = future_epoch_us
            self._release_event.set()

        # Await barrier release event
        await self._release_event.wait()

        return WaitResponse(release=True, synchronized_start_us=self._synchronized_start_us)
```

---

## 4. NUMA Topologies & Hardware Affinity Engine (`steve/orchestrator/affinity.py`)

### 4.1 Dual-Socket Hardware Architecture

```text
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                              DUAL-SOCKET NUMA HARDWARE TOPOLOGY                                 │
├─────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                 │
│   ┌────────────────────────────────────────┐       ┌────────────────────────────────────────┐   │
│   │           NUMA NODE 0 (Socket 0)       │       │           NUMA NODE 1 (Socket 1)       │   │
│   │ ┌──────────────────┐┌────────────────┐ │       │ ┌──────────────────┐┌────────────────┐ │   │
│   │ │ Physical Core 0  ││ Physical Core 1│ │       │ │ Physical Core 2  ││ Physical Core 3│ │   │
│   │ │  (L1/L2 Cache)   ││  (L1/L2 Cache) │ │       │ │  (L1/L2 Cache)   ││  (L1/L2 Cache) │ │   │
│   │ └────────┬─────────┘└────────┬───────┘ │       │ └────────┬─────────┘└────────┬───────┘ │   │
│   │          └─────────┬─────────┘         │       │          └─────────┬─────────┘         │   │
│   │                    ▼                   │       │                    ▼                   │   │
│   │             Shared L3 Cache            │       │             Shared L3 Cache            │   │
│   │                    │                   │       │                    │                   │   │
│   │                    ▼                   │       │                    ▼                   │   │
│   │             Local Node 0 RAM           │       │             Local Node 1 RAM           │   │
│   └────────────────────┬───────────────────┘       └────────────────────┬───────────────────┘   │
│                        │                                                │                       │
│                        └──────────── Inter-Socket Interconnect ─────────┘                       │
│                                      (UPI / Infinity Fabric)                                    │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Core Pinning Mechanics
* **Physical Core Filtering:** Inspects `/sys/devices/system/cpu` to isolate physical cores from SMT hyperthreads.
* **Affinity Locking:** Invokes `os.sched_setaffinity(0, {core_id})` upon worker bootstrap to eliminate L1/L2 cache invalidation and inter-socket bus hops.

---

## 5. Zero-Allocation Structured Async Logging (`steve/logging.py`)

### 5.1 Hot-Path Decoupling Architecture

```text
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 HOT-PATH LOGGING DECOUPLING                                     │
├─────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                 │
│  [ Active Worker Hot Path ]                                                                     │
│               │                                                                                 │
│               ├── 1. Log-Level Gating Check (Is DEBUG enabled?) ──► [ FALSE: Instant 0ns No-Op] │
│               │                                                                                 │
│               ├── 2. IF TRUE: Enqueue tuple to lock-free memory queue (Zero File I/O)           │
│               │                                                                                 │
│  ═════════════╪════════════════════════════════════════════════════════════════════════════════ │
│               │ Process Boundary                                                                │
│               ▼                                                                                 │
│  [ Dedicated Background Logging Worker Thread (AsyncLogQueueHandler) ]                          │
│               │                                                                                 │
│               ├── 3. Drain raw tuples from queue in batches                                     │
│               ├── 4. Format Structured JSON: {"timestamp_ns": ..., "run_id": ..., "msg": ...}  │
│               └── 5. Non-blocking flush to stdout / logfile / ClickHouse Sink                   │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

* **Zero Hot-Path Allocations:** Log-level gating ensures zero string interpolation overhead during active I/O loops.
* **Context Inheritance:** Structured logs automatically bind `run_id`, `node_id`, `core_id`, and ISO-8601 nanosecond timestamps.
