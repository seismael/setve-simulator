---
id: "HLD-DIST-001"
title: "Distributed Control Plane, Barrier Synchronization, & Workload Sharding Engine"
type: "HLD"
status: "APPROVED"
domain: "data-plane"
layer: "compute-engine"
c4_level: "container"
diataxis_type: "explanation"
traceability:
  implements_brd: ["BRD-SETVE-001", "BRD-DIST-001"]
  governed_by_adr: ["ADR-0001", "ADR-0002"]
  parent_hld: "HLD-SETVE-001"
  child_llds: ["LLD-ORCH-001"]
code_references:
  - "setve/orchestrator/master.py"
  - "setve/orchestrator/cluster.py"
  - "setve/orchestrator/sync.py"
test_references:
  - "tests/test_master_telemetry.py"
owner: "@architecture-team"
last_validated_date: "2026-08-05"
---


# HLD-DIST-001: Distributed Control Plane, Barrier Synchronization, & Workload Sharding Engine

## 1. System Context & C4 Architecture (Levels 1 & 2)

HLD-DIST-001 defines the scale-out architecture required to orchestrate multi-node load execution fleets across hundreds of physical servers. It extends `HLD-SETVE-001` from a single-host core-pinned execution model into a shared-nothing, linearly scalable ($\mathcal{O}(N)$) distributed system capable of generating multi-terabyte-per-second ($\text{TB/s}$) aggregate load without centralized lock bottlenecks.


```text
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 DISTRIBUTED HORIZONTAL TOPOLOGY                                 │
├─────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                 │
│                           ┌──────────────────────────────────────────┐                          │
│                           │      SETVE Master Orchestrator Node      │                          │
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

### 1.1 Architectural Subsystems

1. **Global Master Orchestrator:** Manages cluster lifecycle, parses declarative YAML workload blueprints, calculates partition shard layouts, and enforces barrier synchronization phases via gRPC.
2. **Local Node Daemon (`setve-node`):** A lightweight agent running on each compute host that discovers NUMA topology, manages local core pinning (`os.sched_setaffinity`), spawns worker container/process pools, and monitors host memory alignment constraints.
3. **Shared-Nothing Worker Fleet:** Core-pinned Python processes operating in isolation. Workers maintain zero runtime communication with each other during active I/O execution, ensuring strict $\mathcal{O}(N)$ scaling linearity.
4. **Out-of-Band Telemetry Sink:** Independent eBPF/XDP network and block layer probes on each node that export raw wire metrics directly to ClickHouse over dedicated management interfaces.

### 1.2 Vertical vs. Horizontal Scaling Matrix

| Dimension | Vertical Scaling (Intra-Node) | Horizontal Scaling (Inter-Node) |
| :--- | :--- | :--- |
| **Mechanism** | `multiprocessing` + `sched_setaffinity` | gRPC barrier sync + Kubernetes DaemonSet |
| **Concurrency** | 1 isolated process per physical CPU core | 1 to 64+ physical servers |
| **Memory Model** | Page-aligned `mmap` ring buffers ($4096\text{B}$) | Independent physical RAM per server (Shared-Nothing) |
| **Data Hot Path** | Zero-allocation `memoryview` + AVX-512 XOR | Zero inter-node network traffic during I/O |
| **Target Scale** | $\ge 8\text{ GB/s}$ ($64\text{ Gbps}$) per server node | $\ge 1\text{ TB/s}$ ($8\text{ Tbps}$) cluster aggregate |

---

## 2. Workload Sharding & Deterministic Seed Distribution

To guarantee that cluster scaling remains $\mathcal{O}(N)$ without runtime master-worker synchronization, all task properties (target block offsets, stream IDs, and payload entropy patterns) are computed deterministically at initialization.

### 2.1 Throughput Partitioning Equation

Given a target aggregate cluster throughput $T_{\text{total}}$ (e.g., $100\text{ GB/s}$), $N$ registered physical compute nodes, and $K_n$ available physical CPU cores on node $n$:

$$T_{\text{node}_n} = T_{\text{total}} \times \left( \frac{K_n}{\sum_{i=1}^{N} K_i} \right)$$

$$T_{\text{core}_{n,k}} = \frac{T_{\text{node}_n}}{K_n} = \frac{T_{\text{total}}}{\sum_{i=1}^{N} K_i}$$

### 2.2 Deterministic Entropy & Offset Seed Generation

To prevent overlapping write streams or duplicate data blocks without maintaining a shared index, each core worker $(n, k)$ derives its state using a 64-bit split-mix hash derived from a global run seed:

$$\text{Seed}_{\text{worker}(n,k)} = \text{MurmurHash3\_x64\_128}(\text{GlobalRunSeed} \parallel \text{NodeID}_n \parallel \text{CoreID}_k)$$

* **Incompressible Data Pattern:** Each worker initializes its local `PySIMDPayloadMutator` ring buffer using $\text{Seed}_{\text{worker}(n,k)}$, guaranteeing unique non-compressible payloads across the cluster.
* **Block Address Mapping:** Storage offsets follow a strided consistent block calculation:
$$\text{Offset}(t) = \text{BaseOffset} + \left[ (t \times \text{Stride}) + (n \times K + k) \right] \times \text{BlockSize}$$

---

## 3. Two-Phase gRPC Barrier Synchronization Protocol

To prevent test skew caused by worker startup initialization drift (e.g., memory allocations, DNS resolution, socket handshakes), SETVE enforces a **Two-Phase Barrier Synchronization Protocol** prior to triggering active load execution.


```text
Master Orchestrator                  Node Daemon 1                     Node Daemon N
│                                 │                                 │
│ ─── 1. DistributeBlueprint ───► │ ─── 1. DistributeBlueprint ───► │
│                                 │                                 │
│                                 ├── Initialize Workers            ├── Initialize Workers
│                                 ├── Page-Align mmap Buffers       ├── Page-Align mmap Buffers
│                                 ├── Open io_uring Queue           ├── Open io_uring Queue
│                                 │                                 │
│ ◄─── 2. ReadyForBarrier ─────── │ ◄─── 2. ReadyForBarrier ─────── │
│      (State: PREPARED)          │      (State: PREPARED)          │
│                                 │                                 │
[ All Nodes PREPARED ]            │                                 │
│                                 │                                 │
│ ─── 3. ReleaseBarrier ────────► │ ─── 3. ReleaseBarrier ────────► │
│      (Sync Execution Start)     │      (Sync Execution Start)     │
│                                 │                                 │
│                                 ▼                                 ▼
│                           EXECUTE LOAD                      EXECUTE LOAD
│                           (Zero-Copy Loop)                  (Zero-Copy Loop)
│                                 │                                 │
│ ◄─── 4. ExecutionComplete ───── │ ◄─── 4. ExecutionComplete ───── │
│                                 │                                 │
```

### 3.1 Protocol State Machine

1. **State `CONFIGURING`:** Master broadcasts workload blueprints containing target specs, block sizes, entropy ratios, and duration. Node daemons launch core-pinned worker processes.
2. **State `PREPARED` (Phase 1 Barrier):** Workers pre-allocate anonymous page-aligned `mmap` ring buffers ($4096\text{-byte}$ boundary assertions), initialize `io_uring` instances, and issue pre-flight connectivity checks against SUT endpoints. Once ready, the node sends a `ReadyForBarrier` RPC to the master.
3. **State `RUNNING` (Phase 2 Release):** The master waits until 100% of nodes report `PREPARED`. It then issues a synchronized `ReleaseBarrier` gRPC broadcast specifying an exact UNIX microsecond epoch timestamp $t_{\text{start}}$ for simultaneous load execution.
4. **State `TEARDOWN`:** Upon reaching test duration, workers flush pending completion queues, unmap ring buffers, and return total operation counts to the master.

---

## 4. Fault Tolerance, Rebalancing, & Elasticity

### 4.1 Node Eviction & Partition Rebalancing
If a compute node fails heartbeat checks during Phase 1 (`PREPARED`), the Master Orchestrator triggers an automatic shard rebalancing workflow:


```text
[ Heartbeat Timeout (3s) ] ──► [ Mark Node Dead ] ──► [ Recalculate T_core Equation ]
│
▼
[ Cancel Current Run ] ◄── [ Broadcast Re-Shard Blueprint ] ◄─┘
```

If a node drops during Phase 2 (`RUNNING`), the run is flagged as degraded. The master reallocates the failed node's target offset space to active nodes if dynamic scaling is enabled in the blueprint.

---

## 5. gRPC Service Specifications (`setve/orchestrator/sync.proto`)

```protobuf
syntax = "proto3";

package setve.orchestrator;

service ClusterOrchestrator {
  // Master -> Worker Node: Deploy workload blueprint
  rpc DeployBlueprint (BlueprintRequest) returns (BlueprintResponse);
  
  // Worker Node -> Master: Report readiness for barrier release
  rpc SignalReady (ReadySignal) returns (WaitResponse);
  
  // Master -> Worker Node: Stream real-time cluster status & cancellation
  rpc StreamControl (stream ControlSignal) returns (stream NodeStatus);
}

message BlueprintRequest {
  string run_id = 1;
  uint64 global_seed = 2;
  uint64 start_time_epoch_us = 3;
  uint32 duration_seconds = 4;
  string target_uri = 5;
  uint32 block_size_bytes = 6;
  float entropy_ratio = 7;
  uint64 target_throughput_bytes_per_sec = 8;
}

message BlueprintResponse {
  bool success = 1;
  string error_message = 2;
}

message ReadySignal {
  string run_id = 1;
  string node_id = 2;
  uint32 core_count = 3;
  bool memory_aligned = 4;
}

message WaitResponse {
  bool release = 1;
  uint64 synchronized_start_us = 2;
}

message ControlSignal {
  enum Command {
    START = 0;
    PAUSE = 1;
    STOP = 2;
    REBALANCE = 3;
  }
  Command command = 1;
  string run_id = 2;
}

message NodeStatus {
  string node_id = 1;
  uint64 bytes_completed = 2;
  uint64 ops_completed = 3;
  double current_throughput_gbps = 4;
}
```

---

## 6. Architectural Quality Matrix

| Quality Attribute | Architectural Tactic | Metric / Verification |
| --- | --- | --- |
| **Horizontal Scalability** | Shared-nothing core workers; deterministic hash seeding | Linear $\mathcal{O}(N)$ scaling up to 1,024+ physical nodes |
| **Execution Synchronicity** | Microsecond-precision gRPC barrier release | $< 50\,\mu\text{s}$ start drift across nodes |
| **Fault Tolerance** | Automatic heartbeat eviction & shard rebalancing | Dead nodes evicted within $3.0\text{s}$ without hanging cluster |
| **Zero-Copy Hot Path** | Core-pinned `io_uring` + page-aligned `mmap` rings | 0 Python GIL calls or dynamic allocations during active runs |
