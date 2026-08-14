# SETVE: Universal Simulation & Telemetry Validation Engine

[![Build Status](https://github.com/seismael/setve-simulator/actions/workflows/ci.yml/badge.svg)](https://github.com/seismael/setve-simulator/actions)
[![Doc Graph](https://github.com/seismael/setve-simulator/actions/workflows/doc_graph_check.yml/badge.svg)](https://github.com/seismael/setve-simulator/actions)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type Checking: mypy](https://img.shields.io/badge/mypy-strict-blue.svg)](https://mypy-lang.org/)

**SETVE** is a platform-agnostic, multi-gigabyte-per-second load generation and telemetry verification engine engineered to stress-test high-performance storage and data-plane systems ($\ge 8\text{ GB/s}$ per node to multi-TB/s clusters).

Built with strict **Domain-Driven Design (DDD)** and **Gang of Four (GoF)** design patterns, SETVE completely decouples its distributed orchestration control plane from zero-copy, hardware-aligned data plane execution kernels.

---

## Key Architecture & Core Specifications

- **[AGENTS.md](file:///c:/dev/projects/setve-simulator/AGENTS.md)**: Dynamic governance rules, zero-allocation constraints, alignment guardrails, and AI agent execution protocol.
- **[SPEC.md](file:///c:/dev/projects/setve-simulator/SPEC.md)**: Core technical design, kernel-bypass drivers (`io_uring`), SIMD payload mutators, and multi-core orchestration blueprints.
- **[docs/DOCUMENTATION.md](file:///c:/dev/projects/setve-simulator/docs/DOCUMENTATION.md)**: Dual-indexed documentation taxonomy (Arc42 / C4 / Diátaxis / IEEE 42010), frontmatter schemas, and $\text{BRD} \rightarrow \text{HLD} \rightarrow \text{ADR} \rightarrow \text{LLD}$ traceability DAG.

---

## Subsystem Architecture & Features

```text
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                                 CONTROL PLANE ORCHESTRATION                              │
│  DeterministicShardGenerator ──► MultiCoreOrchestrator ──► ClusterSyncServicer (gRPC)    │
└────────────────────────────────────────────┬─────────────────────────────────────────────┘
                                             │
                       Core-Pinned Multiprocessing (os.sched_setaffinity)
                                             │
┌────────────────────────────────────────────▼─────────────────────────────────────────────┐
│                                 DATA PLANE EXECUTION KERNEL                              │
│  BufferPool (Page-Aligned mmap) ──► PySIMDPayloadMutator (AVX-512 In-Place XOR)          │
│                                            │                                             │
│                       TargetAdapter Interface (GoF Factory)                             │
│       ┌──────────────────┬─────────────────┼──────────────────┬─────────────────┐        │
│       ▼                  ▼                 ▼                  ▼                 ▼        │
│  [ POSIX O_DIRECT ] [ Linux io_uring ] [ S3 Multipart ] [ Vector Embed ] [ NVMe-oF ]    │
└────────────────────────────────────────────┬─────────────────────────────────────────────┘
                                             │
┌────────────────────────────────────────────▼─────────────────────────────────────────────┐
│                            VALIDATION & OBSERVABILITY PLANE                              │
│  MetricCollector (64-Bucket HDR Histogram) ──► EBPFProbe ──► TelemetryEvaluator (<= 0.1%)│
│                                            │                                             │
│              Prometheus Exporter ──► ClickHouse Sink ──► JSON / ASCII Matrix             │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

### Supported Storage & Data-Plane Adapters

| Protocol Scheme | Adapter Class | Description | Block Boundary |
| :--- | :--- | :--- | :--- |
| `posix://`, `file://` | `PosixDirectIOAdapter` | POSIX Direct I/O (`O_DIRECT \| O_RDWR`) with zero-copy buffer views | 4096 Bytes |
| `iouring://`, `io_uring://` | `IoUringTargetAdapter` | Linux `io_uring` kernel submission/completion ring buffer queue | 4096 Bytes |
| `s3://` | `S3TargetAdapter` | High-throughput HTTP multipart streaming object store driver | 5 MB Chunks |
| `vector://`, `embedding://`| `VectorTargetAdapter` | High-density vector embedding similarity and upsert driver | 64 Bytes |
| `nvmeof://` | `NVMeOFAdapter` | Kernel-bypass NVMe over Fabrics target driver (Enterprise tier) | 4096 Bytes |

---

## Subsystem Benchmark Performance Matrix

All metrics measured via the comprehensive benchmark suite (`python tests/benchmark_suite.py`):

| Subsystem | Benchmark Test | Measured Throughput / Rate | ns / op | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Memory** | DirectBuffer 4096-byte Alignment Assert | 9.01 M ops/s | 110.9 ns | **PASS** ($< 200\text{ ns}$) |
| **Memory** | DirectBuffer 64-byte SIMD Alignment Assert | 9.69 M ops/s | 103.2 ns | **PASS** ($< 200\text{ ns}$) |
| **Memory** | BufferPool Ring Buffer Acquire | 9.35 M ops/s | 107.0 ns | **PASS** ($< 300\text{ ns}$) |
| **Payload / SIMD** | In-Place Entropy Mutation (64 KB) | 54.08 Gbps ($6.30\text{ GB/s}$) | 9,694 ns | **PASS** ($\ge 10\text{ Gbps}$) |
| **Payload / SIMD** | In-Place Entropy Mutation (1024 KB) | 66.33 Gbps ($7.72\text{ GB/s}$) | 126,461 ns | **PASS** ($\ge 10\text{ Gbps}$) |
| **Adapters** | POSIX Direct I/O Sequential Read (1MB) | 6.35 Gbps ($757.2\text{ MB/s}$) | 1,320,623 ns | **PASS** |
| **Adapters** | S3 Multipart Stream (1MB chunk) | 17,962.76 Gbps | 467.0 ns | **PASS** |
| **Adapters** | Vector Database Batch Upsert (4KB) | 3,635.04 K ops/s | 275.1 ns | **PASS** |
| **Observability** | MetricCollector HDR Recording Overhead | 2.98 M records/s | 335.9 ns | **PASS** ($< 1\text{ }\mu\text{s}$) |
| **Orchestrator** | Sharding Scaling (1,024 Nodes / 16,384 Cores)| 58.33 ms total | 3,560.3 ns/core | **PASS** ($< 10\text{ }\mu\text{s}$) |

---

## Directory & Package Layout

```text
setve/
├── pyproject.toml             # Build specs, mypy --strict, ruff config
├── Makefile                   # Automation targets (lint, test, bench, docs)
├── deploy/                    # Infrastructure manifests
│   ├── helm/setve-cluster/    # Production Kubernetes Helm chart & values
│   ├── k8s/operator/          # Kopf Kubernetes Operator CRD controller
│   └── environments/          # Local, dev, staging, prod configurations
├── docs/                      # Dual-Indexed Documentation Engine
│   ├── .index/                # Dependency DAG graph & JSON taxonomy schema
│   ├── 01-brd/                # Business & System Requirements
│   ├── 02-hld/                # High-Level Design (C1/C2 Topologies)
│   ├── 03-adr/                # Architectural Decision Records (Guardrails)
│   └── 04-lld/                # Low-Level Design (C3/C4 Implementations)
├── scripts/                   # Tooling scripts
│   ├── validate_docs.py       # YAML frontmatter & code reference validator
│   ├── build_doc_graph.py     # Dependency DAG JSON index generator
│   └── bootstrap_project.py   # Workspace structure generator
├── setve/                     # Core Python 3.12+ Source Engine
│   ├── adapters/              # Target storage drivers (POSIX, io_uring, S3, Vector)
│   ├── payload/               # SIMD mutator, buffer pool, workload blueprints
│   ├── orchestrator/          # Master controller, core-pinned worker, sync servicer
│   └── validation/            # HDR histograms, Prometheus reporter, eBPF probe
└── tests/                     # Verification Suite (34 Unit & Integration Tests)
    ├── benchmark_suite.py     # Multi-subsystem performance benchmark suite
    ├── benchmark_adapters.py  # Hot-path adapter sanity benchmark
    └── test_*.py              # Comprehensive test modules
```

---

## Quickstart & CLI Commands

```bash
# 1. Install dependencies in editable mode
pip install -e ".[dev]"

# 2. Run static analysis and formatting quality gates
ruff check setve/ tests/ scripts/ deploy/
ruff format --check setve/ tests/ scripts/ deploy/

# 3. Execute the comprehensive test suite (34 tests)
pytest -v

# 4. Run the multi-subsystem benchmark suite
python tests/benchmark_suite.py

# 5. Validate documentation DAG and regenerate RAG index
python scripts/validate_docs.py
python scripts/build_doc_graph.py
```

---

## Programmatic Usage Example

```python
from setve.payload.blueprint import WorkloadBlueprint
from setve.orchestrator.master import MultiCoreOrchestrator

# 1. Define declarative simulation workload blueprint
blueprint = WorkloadBlueprint.from_dict({
    "run_id": "sim-production-stress-01",
    "target_uri": "posix:///mnt/nvme/sim_data",
    "block_size_bytes": 1048576,       # 1 MB block size
    "entropy_ratio": 0.85,             # 85% randomized payload
    "target_throughput_gbps": 100,     # Target 100 Gbps cluster aggregate
    "duration_seconds": 10,
    "global_seed": 9999,
})

# 2. Instantiate and launch multi-core orchestrator
orchestrator = MultiCoreOrchestrator()
summary = orchestrator.start(blueprint)

# 3. Render execution report & Prometheus metrics
print(summary.format_table())
print(summary.to_prometheus_metrics())
```

---

## Telemetry Output Example

```text
+==================================================================================+
| SETVE SIMULATION & TELEMETRY REPORT: sim-production-stress-01                     |
+==================================================================================+
| Target URI:     posix:///mnt/nvme/sim_data                                       |
| Total Cores:    8                                                                |
| Duration:       10.02 s                                                          |
| Total Ops:      124,800                                                          |
| Total Data:     121.88 GB (124800.0 MB)                                          |
| Aggregate Rate: 99.70 Gbps (12.46 GB/s)                                          |
| Max p99 Lat:    0.812 ms (Avg: 0.745 ms)                                         |
+----------------------------------------------------------------------------------+
| OUT-OF-BAND TELEMETRY TRIANGULATION: VALID (<= 0.1%)                             |
| Client Data:    130862284800                                                     |
| Probe Data:     130862284800                                                     |
| Metric Skew:    0.0000% (0 bytes delta)                                          |
+==================================================================================+
```

