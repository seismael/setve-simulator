---
id: "HLD-SETVE-001"
title: "Universal Simulation Engine System Topology & Data Plane Architecture"
type: "HLD"
status: "APPROVED"
domain: "data-plane"
layer: "compute-engine"
c4_level: "container"
diataxis_type: "explanation"
traceability:
  implements_brd: ["BRD-SETVE-001"]
  governed_by_adr: ["ADR-0001", "ADR-0002"]
  parent_hld: null
  child_llds: ["LLD-MUTATOR-001", "LLD-ADAPTER-001"]
code_references:
  - "setve/orchestrator/master.py"
  - "setve/payload/mutator.py"
  - "setve/adapters/base.py"
test_references:
  - "tests/benchmark_suite.py"
owner: "@architecture-team"
last_validated_date: "2026-08-05"
---


# HLD-SETVE-001: Universal Simulation Engine — System Topology & Data Plane Architecture

## 1. System Context (C4 Levels 1–2)

This document defines the multi-layer, zero-copy architecture required to meet the
line-rate throughput targets established in **BRD-SETVE-001**. Four isolated planes
compose the system:

| Plane | Responsibility | Primary Module |
| ----- | -------------- | -------------- |
| **Control** | Topology discovery, process lifecycle, blueprint parsing | `setve.orchestrator.master` |
| **Compute** | Core-pinned workers, uvloop event loops, payload mutation | `setve.orchestrator.worker`, `setve.payload.mutator` |
| **Interface** | Protocol-agnostic target I/O over `DirectBuffer` | `setve.adapters.*` |
| **Validation** | Out-of-band eBPF telemetry triangulation | `setve.validation.*` |

### 1.1 System Topology Diagram

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                      ORCHESTRATION CONTROL PLANE                       │
│             (Master Controller · Topologies · Blueprints)              │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │  IPC / Shared-Memory Signals
                 ┌───────────────┴───────────────┐
                 ▼                               ▼
┌────────────────────────────────┐ ┌────────────────────────────────┐
│  WORKER 0  (Core-Pinned)       │ │  WORKER N  (Core-Pinned)       │
│ ┌────────────────────────────┐ │ │ ┌────────────────────────────┐ │
│ │ uvloop Event Loop          │ │ │ │ uvloop Event Loop          │ │
│ ├────────────────────────────┤ │ │ ├────────────────────────────┤ │
│ │ PySIMDPayloadMutator       │ │ │ │ PySIMDPayloadMutator       │ │
│ ├────────────────────────────┤ │ │ ├────────────────────────────┤ │
│ │ Page-Aligned Ring Buffer   │ │ │ │ Page-Aligned Ring Buffer   │ │
│ ├────────────────────────────┤ │ │ ├────────────────────────────┤ │
│ │ TargetAdapter (io_uring)   │ │ │ │ TargetAdapter (io_uring)   │ │
│ └─────────────┬──────────────┘ │ │ └─────────────┬──────────────┘ │
└───────────────┼────────────────┘ └───────────────┼────────────────┘
                │  Zero-Copy (O_DIRECT / io_uring) │
                ▼                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       SYSTEM UNDER TEST (SUT)                          │
│            NVMe-oF · POSIX · S3 · Vector DB Targets                   │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │  Out-of-Band Hardware Signals
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                 TELEMETRY TRIANGULATION PLANE                          │
│        eBPF / XDP Probes  →  ClickHouse Analytics Engine              │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Core Subsystems

1. **Master Orchestrator (`setve.orchestrator.master`)**
   Parses workload blueprints, discovers system topology (`lscpu` / NUMA), and
   spawns worker processes pinned 1 : 1 to physical cores via `os.sched_setaffinity`.

2. **Core-Pinned Worker Fleet (`setve.orchestrator.worker`)**
   Independent processes each running an isolated `uvloop` event loop.
   Workers execute zero-allocation loops and report metrics through shared-memory arrays.

3. **SIMD Payload Engine (`setve.payload.mutator`)**
   Manages page-aligned `mmap` ring buffers and mutates entropy ratios
   ($\alpha \in [0.0, 1.0]$) in-place via AVX-512 without Python heap allocations.

4. **Pluggable Target Adapters (`setve.adapters`)**
   Non-blocking interface layer across POSIX, `io_uring`, S3, and Vector APIs—all
   operating on zero-copy `DirectBuffer` instances.

5. **Telemetry & Triangulation (`setve.validation`)**
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
| 5 | **Completion Reaping** | CQE callbacks release the slice back to the ring buffer pool—zero garbage collection. |

---

## 3. Abstract Interface Contracts

### 3.1 `TargetAdapter` ABC (`setve.adapters.base`)

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
    async def read(
        self, target: TargetDescriptor, offset: int, buffer: DirectBuffer
    ) -> int:
        """Async zero-copy read into DirectBuffer. Returns bytes read."""

    @abstractmethod
    async def write(
        self, target: TargetDescriptor, offset: int, payload: DirectBuffer
    ) -> int:
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
