---
id: "HLD-STEVE-001"
title: "Universal Simulation Engine System Topology & Data Plane Architecture"
type: "HLD"
status: "APPROVED"
domain: "data-plane"
layer: "compute-engine"
c4_level: "container"
diataxis_type: "explanation"
traceability:
  implements_brd: ["BRD-STEVE-001"]
  governed_by_adr: ["ADR-0001", "ADR-0002"]
  parent_hld: null
  child_llds: ["LLD-MUTATOR-001", "LLD-ADAPTER-001", "LLD-VAL-001"]
code_references:
  - "steve/orchestrator/master.py"
  - "steve/payload/mutator.py"
  - "steve/adapters/base.py"
test_references:
  - "tests/benchmark_suite.py"
owner: "@architecture-team"
last_validated_date: "2026-08-05"
---



# HLD-STEVE-001: Universal Simulation Engine — System Topology & Data Plane Architecture

## 1. System Context (C4 Levels 1–2)

This document defines the multi-layer, zero-copy architecture required to meet the
line-rate throughput targets established in **BRD-STEVE-001**. Four isolated planes
compose the system:

| Plane | Responsibility | Primary Module |
| ----- | -------------- | -------------- |
| **Control** | Topology discovery, process lifecycle, blueprint parsing | `steve.orchestrator.master` |
| **Compute** | Core-pinned workers, uvloop event loops, payload mutation | `steve.orchestrator.worker`, `steve.payload.mutator` |
| **Interface** | Protocol-agnostic target I/O over `DirectBuffer` | `steve.adapters.*` |
| **Validation** | Out-of-band eBPF telemetry triangulation | `steve.validation.*` |

### 1.0 System Context Diagram (C1)

```text
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                SYSTEM CONTEXT (C1)                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   ┌───────────────────────────┐                ┌────────────────────────────┐   │
│   │ STEVE Distributed Cluster │  Stress Load   │ System Under Test (SUT)    │   │
│   │ (4-64 Core-Pinned Nodes)  │ ─────────────> │ (NVMe-oF / POSIX / S3 / DB)│   │
│   └─────────────┬─────────────┘                └─────────────┬──────────────┘   │
│                 │                                            │                  │
│                 │ In-Band Client Telemetry                   │ SUT Telemetry    │
│                 v                                            v                  │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                   METRIC TRIANGULATION & ARBITRATION                    │   │
│   │   (Validates if SUT matches physical Linux eBPF / XDP wire reality)     │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 1.1 3-Plane Subsystem Topology Diagram (C2)

```text
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                                 STEVE 3-PLANE TOPOLOGY (C2)                              │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│ 1. CONTROL PLANE (Master Orchestrator)                                                   │
│    ┌──────────────────┐    gRPC Barrier Sync    ┌───────────────────────────────────┐    │
│    │  Master Process  │ ──────────────────────> │ Core-Pinned Worker Processes (0..N)│   │
│    └────────┬─────────┘                         └─────────────────┬─────────────────┘    │
│             │ Topology Sharding                                   │                      │
│             v                                                     v                      │
│ 2. DATA PLANE (Zero-Allocation Hot Path)                                                 │
│    ┌────────────────────────────────────────────────────────────────────────────────┐    │
│    │  mmap Ring Buffer Pool  ──>  SIMD Payload Mutator  ──>  Target Adapters (I/O)  │    │
│    │  (4096B Page-Aligned)        (AVX-512 In-Place)         (POSIX O_DIRECT, S3)   │    │
│    └──────────────────────────────────────────────────────────────┬─────────────────┘    │
│                                                                   │                      │
│ 3. VALIDATION PLANE (Ground-Truth Arbitration)                    │                      │
│    ┌───────────────────────────────┐                              │                      │
│    │ Linux eBPF / XDP Probe        │ (Out-of-Band Physical Bytes) │                      │
│    └──────────────┬────────────────┘                              │                      │
│                   │                                               │                      │
│                   v                                               v                      │
│    ┌────────────────────────────────────────────────────────────────────────────────┐    │
│    │ Dual-Source Telemetry Evaluator (Mathematical Skew Verification <= 0.1%)       │    │
│    │ Export Formats: ASCII Matrix | Prometheus (/metrics) | Structured JSON          │    │
│    └────────────────────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Hot-Path Memory & Vector Layout (C4)

```text
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     HOT PATH MEMORY & VECTOR LAYOUT (C4)                        │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  1. Hardware Page-Aligned Buffer Pool (4096-Byte Boundaries)                    │
│     ┌──────────────────┬──────────────────┬──────────────────┬──────────────┐   │
│     │ Slot 0 (4096B)   │ Slot 1 (4096B)   │ Slot 2 (4096B)   │ Slot N...    │   │
│     └──────────────────┴──────────────────┴──────────────────┴──────────────┘   │
│     Allocated via mmap (POSIX) / VirtualAlloc (Windows)                         │
│                                                                                 │
│  2. In-Place AVX-512 SIMD Mutation (Zero Python Allocations)                    │
│     ┌───────────────────────────────────────────────────────────────────────┐   │
│     │ memoryview(raw_buffer)[offset : offset + length]                      │   │
│     │ └─> np.bitwise_xor(view, entropy_mask, out=view)                     │   │
│     └───────────────────────────────────────────────────────────────────────┘   │
│     Mutates entropy directly in existing physical RAM without copying data.     │
│                                                                                 │
│  3. Direct I/O Submission                                                       │
│     os.write(fd, buffer.view) / io_uring SQE -> Block Device Controller         │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 Core Subsystems

1. **Master Orchestrator (`steve.orchestrator.master`)**
   Parses workload blueprints, discovers system topology (`lscpu` / NUMA), and
   spawns worker processes pinned 1 : 1 to physical cores via `os.sched_setaffinity`.

2. **Core-Pinned Worker Fleet (`steve.orchestrator.worker`)**
   Independent processes each running an isolated `uvloop` event loop.
   Workers execute zero-allocation loops and report metrics through shared-memory arrays.

3. **SIMD Payload Engine (`steve.payload.mutator`)**
   Manages page-aligned `mmap` ring buffers and mutates entropy ratios
   ($\alpha \in [0.0, 1.0]$) in-place via AVX-512 without Python heap allocations.

4. **Pluggable Target Adapters (`steve.adapters`)**
   Non-blocking interface layer across POSIX, `io_uring`, S3, and Vector APIs—all
   operating on zero-copy `DirectBuffer` instances.

5. **Telemetry & Triangulation (`steve.validation`)**
   Collects µs-bucketed HDRHistogram latencies client-side and cross-evaluates
   against kernel eBPF/XDP NIC and block counters.

---

## 2. Data Pipeline — Zero-Copy Execution Model

### 2.1 Pipeline Stages

```text
[ Page-Aligned mmap Ring Buffer ]
        │
        ▼
  1. Lease slice → DirectBuffer
        │
        ▼
  2. In-place SIMD mutation (AVX-512 registers)
        │
        ▼
  3. Submit SQE → io_uring / O_DIRECT kernel path
        │
        ▼
  4. DMA pass (host RAM ↔ NIC / NVMe — bypasses page cache)
        │
        ▼
  5. Reap CQE → recycle buffer slot (no GC)
```

### 2.2 Stage Details

| # | Stage | Description |
|---|-------|-------------|
| 1 | **Buffer Leasing** | Worker leases an aligned slice from the `mmap` ring ($4096\text{-byte}$ block, $64\text{-byte}$ SIMD alignment). |
| 2 | **In-Place Mutation** | `PySIMDPayloadMutator` vectorizes block mutations in C/SIMD using a static mask for target entropy $\alpha$. |
| 3 | **Queue Submission** | Worker passes the `DirectBuffer` slice directly to the `TargetAdapter` (e.g., SQE into `io_uring`). |
| 4 | **DMA Execution** | Kernel DMA engines transfer data directly from pinned host memory, bypassing OS page caches. |

### 2.3 10 Production Workload Profiles & Chaos Engineering Matrix

| # | Scenario Script | Domain | Target Subsystem | Primary Engineering Metric |
| :--- | :--- | :--- | :--- | :--- |
| **01** | `usecase_01_storage_stress.py` | Data Plane | `PosixDirectIOAdapter`, `MultiCoreOrchestrator` | Aggregate Gbps, IOPS, Core Pinning, Tail Latency |
| **02** | `usecase_02_dedup_compression.py` | Payload Engine | `PySIMDPayloadMutator`, AVX-512 SIMD | Shannon Entropy, Zlib Savings %, Dedup Ratio |
| **03** | `usecase_03_prometheus_monitoring.py` | Observability | `MetricCollector`, Prometheus `/metrics`, JSON | Sub-ms Latency Percentiles ($p_{50}, p_{90}, p_{99}$), Scrape Export |
| **04** | `usecase_04_ebpf_triangulation.py` | Validation | `EBPFProbe`, `TelemetryEvaluator` | Wire vs Client Skew ($\le 0.1\%$ SLA), MTU/Packet Drops |
| **05** | `usecase_05_ai_vector_s3.py` | Target Drivers | `VectorTargetAdapter`, `S3TargetAdapter` | Upsert IOPS, Concurrent Top-K Nearest-Neighbor QPS |
| **06** | `usecase_06_ai_kv_cache_checkpointing.py` | AI Data Plane | Prefill Burst, PagedAttention KV-Cache | Time-To-First-Token (TTFT), ITL ($p_{50}, p_{90}, p_{99}$) |
| **07** | `usecase_07_multitenant_qos_noisy_neighbor.py` | Control Plane | Multi-Tenant QoS, Token-Bucket | Tail Inflation Ratio ($p_{99}$ Jitter Multiplier), SLA Restoration |
| **08** | `usecase_08_chaos_node_failure.py` | Distributed | `DeterministicShardGenerator`, Node Eviction | Dynamic Shard Rebalance Latency ($\mu\text{s}$), SplitMix64 Uniformity |
| **09** | `usecase_09_storage_tiering_lifecycle.py` | Target Flow | Hot NVMe $\rightarrow$ Warm Block $\rightarrow$ Cold S3 | Lifecycle Storage Cost Reduction (% ROI), 3-Year Enterprise TCO |
| **10** | `usecase_10_tail_latency_microburst.py` | Observability | 64-Bucket HDR Histogram, Microburst Spikes | $p_{99.9} / p_{99.99}$ Tail Latency Degradation, Percentile Tags |

### 2.4 Workload Blueprint DSL & Dynamic Phase Engine (`steve/payload/blueprint.py`)

Workloads in STEVE are defined declaratively via YAML or JSON schemas, decoupling the benchmark profile from the execution runtime.

```text
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                               MULTI-PHASE WORKLOAD STATE MACHINE                                │
├─────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                 │
│   ┌──────────────────┐    Ramp Rate (Gbps/s)    ┌──────────────────┐    Steady Load Duration    │
│   │  Phase 1: WARMUP │ ───────────────────────> │ Phase 2: RAMP-UP │ ─────────────────────────┐ │
│   │ (Pre-fill Cache) │                          │ (0 -> 100 Gbps)  │                          │ │
│   └──────────────────┘                          └──────────────────┘                          │ │
│                                                                                               │ │
│   ┌──────────────────┐    Graceful Flushes      ┌──────────────────┐                          │ │
│   │Phase 4: COOLDOWN │ <─────────────────────── │Phase 3: STEADY   │ <────────────────────────┘ │
│   │(Verify Drains)   │                          │(SLA Measurement) │                            │
│   └──────────────────┘                          └──────────────────┘                            │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

#### Blueprint Features
1. **Multi-Phase Execution:** Automatic state machine managing Warmup $\rightarrow$ Ramp-Up $\rightarrow$ Steady State $\rightarrow$ Cooldown.
2. **Workload Mixture:** Configurable read/write ratios (e.g. 70/30), block size probability distributions (e.g., $60\%$ 4KB, $30\%$ 64KB, $10\%$ 1MB), and dynamic entropy targets ($\alpha \in [0.0, 1.0]$).
3. **Automated SLA Validation:** Declares pass/fail criteria for throughput bounds, $p_{99}$ latency thresholds, and maximum allowable eBPF telemetry skew ($\le 0.1\%$).

---

### 3.1 `TargetAdapter` ABC (`steve.adapters.base`)

All target drivers implement this contract to maintain full decoupling from worker event loops:

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any


@dataclass(slots=True, frozen=True)
class DirectBuffer:
    """Page-aligned, zero-copy memory slice."""

    address: int
    size: int
    alignment: int
    view: memoryview


@dataclass(slots=True, frozen=True)
class TargetDescriptor:
    """Endpoint addressing metadata."""

    endpoint_uri: str
    resource_path: str
    metadata: Dict[str, str]


class TargetAdapter(ABC):
    """Async, zero-copy target driver interface."""

    @abstractmethod
    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize sockets, ring queues, or device handles."""

    @abstractmethod
    async def read(self, target: TargetDescriptor, offset: int, buffer: DirectBuffer) -> int:
        """Async zero-copy read into DirectBuffer. Returns bytes read."""

    @abstractmethod
    async def write(self, target: TargetDescriptor, offset: int, payload: DirectBuffer) -> int:
        """Async zero-copy write from DirectBuffer. Returns bytes written."""

    @abstractmethod
    async def flush(self, target: TargetDescriptor) -> None:
        """Drain all in-flight operations for the given target."""
```

---

## 4. Cross-Cutting Engineering Strategies

### 4.1 Memory Isolation & Alignment

| Constraint | Requirement | Rationale |
|------------|-------------|-----------|
| **Direct I/O** | Buffer address, offset, and length ≡ 0 (mod 4096) | Kernel rejects unaligned `O_DIRECT` requests |
| **SIMD** | Buffer address ≡ 0 (mod 64) | `_mm512_load_si512` requires 64-byte alignment |

**Guaranteed alignment property:**

$$\text{addr} \bmod 4096 = 0 \;\Longrightarrow\; \text{addr} \bmod 64 = 0$$

Since 4096 is a multiple of 64, satisfying the storage constraint automatically
satisfies the SIMD constraint.

### 4.2 Concurrency & GIL Bypass

Threading is **prohibited** on data paths. Each physical core maps to exactly one
worker process with its own `uvloop` and `io_uring` instance:

```text
Physical Core 0  →  Process 0 (Worker)  →  uvloop 0  →  io_uring 0
Physical Core 1  →  Process 1 (Worker)  →  uvloop 1  →  io_uring 1
         ...
Physical Core N  →  Process N (Worker)  →  uvloop N  →  io_uring N
```

This guarantees zero GIL contention and achieves ≥ 8 GB/s per node throughput.

### 4.3 Telemetry Triangulation

The validation engine computes **Metric Skew** ($\delta$) to detect dishonest
SUT telemetry:

$$\delta = \left| \frac{\text{Bytes}_{\text{SUT}} - \text{Bytes}_{\text{Client}}}{\text{Bytes}_{\text{eBPF NIC}}} \right| \times 100$$

* $\delta \le 0.1\%$ → **PASS** — telemetry is trustworthy.
* $\delta > 0.1\%$ → **ALARM** — SUT is over-reporting (e.g., counting cached
  writes before persistence) or dropping metrics.

---

## 5. Architectural Quality Matrix

| Quality Attribute | Tactic | Verification Target |
| --- | --- | --- |
| **Performance** | `io_uring` + `O_DIRECT` + AVX-512 SIMD | ≥ 8 GB/s throughput; < 1% CPU overhead |
| **Scalability** | Core-pinned process isolation | Linear scaling: 1 → 128+ cores |
| **Extensibility** | `TargetAdapter` ABC | New protocols added without orchestrator changes |
| **Observability** | eBPF probes + ClickHouse | µs-resolution histograms; ≤ 0.1% telemetry error |
