# SETVE: Universal Simulation & Telemetry Validation Engine

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version: v0.2.0](https://img.shields.io/badge/version-v0.2.0-blue.svg)](https://github.com/seismael/setve-simulator/releases)
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

```text
                                 [ BRD-SETVE-001 ]        [ BRD-DIST-001 ]
                                         │                       │
                       ┌─────────────────┴───────────────────────┴─────────────────┐
                       ▼                                                           ▼
                [ HLD-SETVE-001 ]                                           [ HLD-DIST-001 ]
                       │                                                           │
          ┌────────────┼────────────┐                                 ┌────────────┴────────────┐
          ▼            ▼            ▼                                 ▼                         ▼
     [ ADR-0001 ]  [ ADR-0002 ] [ HLD-ENV-001 ]                  [ HLD-K8S-001 ]          [ LLD-ORCH-001 ]
          │                         │                                 │
     ┌────┴────────────┐            │                                 │
     ▼                 ▼            ▼                                 ▼
[ LLD-ADAPTER-001 ][ LLD-MUTATOR-001 ][ LLD-VAL-001 ]             [ LLD-K8S-001 ]
```


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
├── usecases/                  # Standalone Production Use Cases & Scenarios
│   ├── README.md              # Scenario execution guide
│   ├── usecase_01_storage_stress.py       # NVMe & Direct I/O Saturation
│   ├── usecase_02_dedup_compression.py    # Inline Deduplication & SIMD Sweeps
│   ├── usecase_03_prometheus_monitoring.py# Live Prometheus & JSON Exporter
│   ├── usecase_04_ebpf_triangulation.py   # Out-of-Band Skew Triangulation
│   └── usecase_05_ai_vector_s3.py         # AI Embedding & S3 Multipart
└── tests/                     # Verification Suite (40 Unit & Integration Tests)
    ├── benchmark_suite.py     # Multi-subsystem performance benchmark suite
    ├── benchmark_adapters.py  # Hot-path adapter sanity benchmark
    ├── test_usecases.py       # End-to-end use case verification suite
    └── test_*.py              # Comprehensive unit/integration tests
```

---

## Quickstart & CLI Commands

```bash
# 1. Install dependencies in editable mode
pip install -e ".[dev]"

# 2. Run static analysis and formatting quality gates
ruff check setve/ tests/ scripts/ deploy/ usecases/
ruff format --check setve/ tests/ scripts/ deploy/ usecases/

# 3. Execute the comprehensive test suite (40 tests)
pytest -v

# 4. Run the multi-subsystem benchmark suite
python tests/benchmark_suite.py

# 5. Run production use case scenarios
python usecases/usecase_01_storage_stress.py
python usecases/usecase_02_dedup_compression.py
python usecases/usecase_03_prometheus_monitoring.py
python usecases/usecase_04_ebpf_triangulation.py
python usecases/usecase_05_ai_vector_s3.py

# 6. Validate documentation DAG and regenerate RAG index
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

---

## Standalone Production Use Cases

The [`usecases/`](file:///c:/dev/projects/setve-simulator/usecases/README.md) catalog provides standalone executable scenario recipes:

| Scenario | Script Path | Description |
| :--- | :--- | :--- |
| **01. NVMe Direct I/O** | [`usecases/usecase_01_storage_stress.py`](file:///c:/dev/projects/setve-simulator/usecases/usecase_01_storage_stress.py) | Saturates local NVMe block devices via zero-copy `O_DIRECT`. |
| **02. Dedup & Compression** | [`usecases/usecase_02_dedup_compression.py`](file:///c:/dev/projects/setve-simulator/usecases/usecase_02_dedup_compression.py) | Benchmarks SIMD payload mutator across compressibility sweeps ($15.5\text{ GB/s}$). |
| **03. Prometheus Monitoring** | [`usecases/usecase_03_prometheus_monitoring.py`](file:///c:/dev/projects/setve-simulator/usecases/usecase_03_prometheus_monitoring.py) | Emits live Prometheus `/metrics` exposition and ClickHouse JSON telemetry. |
| **04. eBPF Triangulation** | [`usecases/usecase_04_ebpf_triangulation.py`](file:///c:/dev/projects/setve-simulator/usecases/usecase_04_ebpf_triangulation.py) | Mathematically audits client metrics vs kernel interface wire counters ($\le 0.1\%$). |
| **05. AI Vector & S3** | [`usecases/usecase_05_ai_vector_s3.py`](file:///c:/dev/projects/setve-simulator/usecases/usecase_05_ai_vector_s3.py) | Simulates parallel vector embedding upserts and S3 multipart streaming. |
| **06. AI KV-Cache & Checkpoints** | [`usecases/usecase_06_ai_kv_cache_checkpointing.py`](file:///c:/dev/projects/setve-simulator/usecases/usecase_06_ai_kv_cache_checkpointing.py) | Models LLM prefill burst, random KV-cache decode, and weight checkpoints. |
| **07. Multi-Tenant QoS** | [`usecases/usecase_07_multitenant_qos_noisy_neighbor.py`](file:///c:/dev/projects/setve-simulator/usecases/usecase_07_multitenant_qos_noisy_neighbor.py) | Evaluates mission-critical SLA ($p_{99} \le 2\text{ms}$) vs noisy-neighbor saturation. |
| **08. Chaos & Shard Rebalance** | [`usecases/usecase_08_chaos_node_failure.py`](file:///c:/dev/projects/setve-simulator/usecases/usecase_08_chaos_node_failure.py) | Simulates $25\%$ node failure and dynamic gap-free shard rebalancing. |
| **09. Multi-Tier Lifecycle** | [`usecases/usecase_09_storage_tiering_lifecycle.py`](file:///c:/dev/projects/setve-simulator/usecases/usecase_09_storage_tiering_lifecycle.py) | Models data aging across Hot NVMe $\rightarrow$ Warm Block $\rightarrow$ Cold S3. |
| **10. Tail Micro-Burst Analysis** | [`usecases/usecase_10_tail_latency_microburst.py`](file:///c:/dev/projects/setve-simulator/usecases/usecase_10_tail_latency_microburst.py) | Injects $50\text{ms}$ $100\times$ traffic surges capturing $p_{99.9} / p_{99.99}$ HDR latency spikes. |


---

## Deployment & Infrastructure Topologies

SETVE supports a comprehensive 3-tier enterprise deployment ecosystem documented in [`deploy/`](file:///c:/dev/projects/setve-simulator/deploy/README.md):

1. **Packaging Specs ([`deploy/packaging/`](file:///c:/dev/projects/setve-simulator/deploy/packaging))**: Multi-stage Linux Docker build (`deploy/packaging/docker/Dockerfile`), production Helm 3 chart (`deploy/packaging/helm/setve-cluster`), and Kopf Kubernetes CRD Operator (`deploy/packaging/operator/controller.py`).
2. **Environment Overlays ([`deploy/environments/`](file:///c:/dev/projects/setve-simulator/deploy/environments/README.md))**: Progressive target tiers across `local` (`docker compose -f deploy/environments/local/docker-compose.yml up -d`), `dev` (Terraform IaaS), `staging` ($100\text{ Gbps}$ bare-metal), and `prod` ($\ge 1\text{ TB/s}$ hyperscale).
3. **Local Cluster Emulator ([`deploy/emulator/`](file:///c:/dev/projects/setve-simulator/deploy/emulator/README.md))**: Multi-node distributed load generator simulator running core-pinned worker fleets with live gRPC barrier synchronization on local host infrastructure.

---

## Community & Contributing

We welcome contributions from systems engineers, storage architects, and data-plane developers!

- **[CONTRIBUTING.md](file:///c:/dev/projects/setve-simulator/CONTRIBUTING.md)**: Developer setup, coding standards, architectural guardrails, and PR guidelines.
- **[CODE_OF_CONDUCT.md](file:///c:/dev/projects/setve-simulator/CODE_OF_CONDUCT.md)**: Contributor Covenant standards.
- **[SECURITY.md](file:///c:/dev/projects/setve-simulator/SECURITY.md)**: Security policy and vulnerability disclosure procedures.

---

## License & Copyright

SETVE is distributed under the **[MIT License](file:///c:/dev/projects/setve-simulator/LICENSE)**.

```text
Copyright (c) 2026 SETVE Contributors
Licensed under the MIT License. See LICENSE file for full details.
```



