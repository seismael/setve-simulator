# SETVE: Universal Simulation & Telemetry Validation Engine

**SETVE** is a platform-agnostic, infinitely scalable load generation and telemetry verification engine engineered to stress-test high-performance storage and data-plane systems ($\ge 8\text{ GB/s}$ per node to multi-TB/s clusters).

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
