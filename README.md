# SETVE: Universal Simulation & Telemetry Validation Engine

[![Build Status](https://github.com/seismael/setve-simulator/actions/workflows/ci.yml/badge.svg)](https://github.com/seismael/setve-simulator/actions)
[![Doc Graph](https://github.com/seismael/setve-simulator/actions/workflows/doc_graph_check.yml/badge.svg)](https://github.com/seismael/setve-simulator/actions)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

**SETVE** is a platform-agnostic, infinitely scalable load generation and telemetry verification engine engineered to stress-test high-performance storage and data-plane systems ($\ge 8\text{ GB/s}$ per node to multi-TB/s clusters). Built from the ground up using strict Domain-Driven Design (DDD) and Gang of Four (GoF) patterns, it completely decouples the distributed control plane from zero-copy, hardware-aligned data planes.

## Key Architecture & Specifications

- **[AGENTS.md](file:///c:/dev/projects/simulate/AGENTS.md)**: Dynamic governance rules, zero-allocation constraints, alignment guardrails, and AI agent workflows.
- **[SPEC.md](file:///c:/dev/projects/simulate/SPEC.md)**: Core technical design, subsystem specs, kernel bypass drivers (`io_uring`), SIMD payload mutators, and multi-core orchestration blueprints.
- **[docs/DOCUMENTATION.md](file:///c:/dev/projects/simulate/docs/DOCUMENTATION.md)**: Dual-indexed documentation taxonomy (Arc42 / C4 / Diátaxis / IEEE 42010), frontmatter schemas, and BRD $\rightarrow$ HLD $\rightarrow$ ADR $\rightarrow$ LLD traceability DAG.

## Project Layout

```text
setve/
├── .github/workflows/         # CI/CD and doc graph validation
├── .index/                    # AI Agent RAG graph index & taxonomy schema
├── docs/                      # Dual-indexed architectural documentation
│   ├── 01-brd/                # Business & System Requirements
│   ├── 02-hld/                # High-Level Design (C1/C2)
│   ├── 03-adr/                # Architecture Decision Records (Guardrails)
│   └── 04-lld/                # Low-Level Design (C3/C4)
├── scripts/                   # Workspace bootstrap & RAG index builder
├── setve/                     # Core Python 3.12+ source package
│   ├── adapters/              # POSIX O_DIRECT, io_uring, S3, Vector drivers
│   ├── payload/               # SIMD mutator & mmap ring buffer pool
│   ├── orchestrator/          # Multi-process core-pinned control plane
│   └── validation/            # eBPF probes & telemetry evaluator
└── tests/                     # Memory alignment, SIMD bounds, benchmark suites
```

## Quickstart Commands

```bash
# Install dependencies in editable mode
make install

# Run static checks and strict typing
make lint
make typecheck

# Run test suite
make test

# Rebuild AI Agent RAG index
make docs-index
```

## Running a Simulation

SETVE uses declarative `WorkloadBlueprint` definitions to drive execution.

```python
from setve.payload.blueprint import WorkloadBlueprint
from setve.orchestrator.master import MultiCoreOrchestrator

blueprint = WorkloadBlueprint(
    run_id="production-stress-test",
    target_uri="iouring:///dev/nvme0n1",
    target_throughput_gbps=100,
    duration_seconds=30
)

orchestrator = MultiCoreOrchestrator()
orchestrator.start(blueprint)
```
