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
  implements_brd: ["BRD-SETVE-001", "BRD-DIST-001"]
  governed_by_adr: ["ADR-0001", "ADR-0002"]
  parent_hld: "HLD-DIST-001"
  child_llds: []
code_references:
  - "setve/orchestrator/master.py"
  - "setve/orchestrator/sync.py"
test_references: []
owner: "@architecture-team"
last_validated_date: "2026-08-05"
---

# LLD-ORCH-001: Master Orchestrator Process Manager & gRPC Synchronization Engine

## 1. Module Overview & Class Structure

`LLD-ORCH-001` provides the low-level technical specification for `MasterOrchestrator` and `ClusterOrchestratorServicer`. The module manages master control-plane state, distributes deterministic workload shards, and executes the two-phase gRPC barrier release sequence across registered cluster nodes.

```text
┌─────────────────────────────────────────────────────────────┐
│             setve.orchestrator.master.MasterOrchestrator    │
├─────────────────────────────────────────────────────────────┤
│ - cluster_nodes: Dict[str, NodeRegistration]               │
│ - barrier_state: BarrierStateEnum                           │
│ - synchronized_start_us: int                                │
├─────────────────────────────────────────────────────────────┤
│ + start_cluster(blueprint: WorkloadBlueprint) -> None       │
│ + register_node(node_id: str, cores: int) -> None           │
│ + calculate_shards(total_throughput: int) -> Dict[str, int] │
│ + release_barrier() -> int                                  │
└──────────────────────────────┬──────────────────────────────┘
│ Serves
▼
┌─────────────────────────────────────────────────────────────┐
│       setve.orchestrator.sync.ClusterOrchestratorServicer   │
├─────────────────────────────────────────────────────────────┤
│ + DeployBlueprint(request, context) -> BlueprintResponse    │
│ + SignalReady(request, context) -> WaitResponse             │
│ + StreamControl(request_iterator, context) -> NodeStatus    │
└─────────────────────────────────────────────────────────────┘
```

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

## 3. Barrier Synchronization Servicer (`setve/orchestrator/sync.py`)

```python
"""gRPC Servicer enforcing two-phase cluster barrier synchronization."""

import asyncio
import time
from typing import Dict, Any
from setve.orchestrator.sync_pb2 import (
    BlueprintRequest,
    BlueprintResponse,
    ReadySignal,
    WaitResponse,
)
from setve.orchestrator.sync_pb2_grpc import ClusterOrchestratorServicer


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

        return WaitResponse(
            release=True,
            synchronized_start_us=self._synchronized_start_us
        )
```
