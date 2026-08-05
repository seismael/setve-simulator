# AGENTS.md: Universal Simulation & Telemetry Validation Engine (SETVE)

## Dynamic Governance & Self-Evolution Protocol

> **MANDATORY PRE-EXECUTION STEP:** On **EVERY** user request, agents MUST first perform a behavioral evaluation pass.

1. **Evaluate Behavioral Signals:** Analyze user requests for feedback, complaints, operational preferences, architectural corrections, test generation rules, or workflow expectations.
2. **Dynamic Governance Update:** If any actionable behavioral guideline or constraint is identified (e.g., test structure preferences, directory layout changes, code style adjustments, documentation rules, or requirement ID updates), **immediately edit `AGENTS.md`** to permanently codify the new rule under Technical Guardrails or Coding Standards **BEFORE** executing the task.
3. **Consistent Enforcement:** All future steps and agent sessions MUST strictly enforce the dynamically updated rules in `AGENTS.md`.

---

## Project Vision & System Context
**SETVE** is a platform-agnostic load generation and telemetry verification framework engineered to stress-test high-performance storage and data-plane systems ($\ge 8\text{ GB/s}$ per node to multi-TB/s clusters) across NVMe-oF, POSIX Direct I/O, S3 object stores, vector databases, and AI prefill/decode pipelines.

Primary runtime: **Python 3.12+**.
For detailed technical design and implementation blueprints, refer to [SPEC.md](file:///c:/dev/projects/simulate/SPEC.md) and [docs/DOCUMENTATION.md](file:///c:/dev/projects/simulate/docs/DOCUMENTATION.md).

---

## Directory & Package Layout

```
setve/
├── __init__.py
├── pyproject.toml             # Build specs, mypy --strict, ruff config
├── adapters/                  # Protocol & Storage Target Drivers
│   ├── __init__.py
│   ├── base.py                # TargetAdapter ABC, DirectBuffer, TargetDescriptor
│   ├── posix.py               # POSIX O_DIRECT File System Adapter
│   ├── io_uring.py            # Linux io_uring Zero-Copy Adapter
│   ├── s3.py                  # Object Storage Adapter
│   └── vector.py              # High-density Vector/Embedding API Adapter
├── payload/                   # Data Generation & Entropy Engines
│   ├── __init__.py
│   ├── mutator.py             # PySIMDPayloadMutator (NumPy / C SIMD)
│   ├── buffer_pool.py         # Page-aligned mmap Ring Buffer Allocator
│   └── profiles.py            # Workload profiles (AI prefill, video, logs)
├── orchestrator/              # Multi-Process Control Plane
│   ├── __init__.py
│   ├── master.py              # Process lifecycle & topology management
│   ├── worker.py              # Core-pinned worker uvloop execution engine
│   └── affinity.py            # Hardware topology & CPU core affinity utilities
├── validation/                # Ground-Truth Metric Triangulation
│   ├── __init__.py
│   ├── ebpf_probe.py          # Native Linux eBPF/XDP interface counters
│   ├── metric_collector.py    # Sub-millisecond HDRHistogram collectors
│   └── evaluator.py           # Divergence math & telemetry accuracy calculation
└── tests/                     # Verification Suite
    ├── test_alignment.py      # 4096-byte and 64-byte alignment integrity tests
    ├── test_mutator.py        # SIMD payload entropy mathematical bounds
    └── benchmark_adapters.py  # Hot-path latency & throughput sanity checks

docs/                          # Dual-Indexed Documentation Engine (docs/DOCUMENTATION.md)
├── .index/                    # Dependency DAG graph & JSON taxonomy schema
├── 01-brd/                    # Business & System Requirements (BRD)
├── 02-hld/                    # C1/C2 System Topology & High-Level Design (HLD)
├── 03-adr/                    # Architectural Decision Records — Guardrails (ADR)
└── 04-lld/                    # C3/C4 Component Architecture & Memory Layout (LLD)
```

---

## Technical Guardrails for AI Agents

AI agents MUST adhere to these non-negotiable architectural mandates:

### 1. Zero Allocations in Hot Paths
* **Constraint:** No heap object instantiations (`dict`, `list`, new class instances, string concatenations) inside active read/write loops or payload mutation passes.
* **Enforcement:** Pre-allocate all memory in page-aligned `mmap` ring buffers during initialization. Slices must use native Python `memoryview` objects.

### 2. Strict Core Isolation & Concurrency
* **Constraint:** Do not use Python threads (`threading`) for I/O execution or compute tasks due to GIL contention.
* **Enforcement:** Execute data-plane workloads using `multiprocessing`. Bind each process to a physical CPU core via `os.sched_setaffinity`. Each process maintains an isolated `uvloop` event loop and `io_uring` instance.

### 3. Hardware-Level Alignment Verification
* **Constraint:** Direct I/O (`O_DIRECT`) kernel requests fail unless buffers, offsets, and lengths align with physical block boundaries.
* **Enforcement:** Enforce $4096\text{-byte}$ alignment for direct storage buffers and $64\text{-byte}$ alignment for AVX-512 SIMD vector operations. Include `DirectBuffer` alignment assertions prior to adapter submissions.

### 4. Interface Segregation & Driver Agnosticism
* **Constraint:** Orchestration engine and payload mutators must never depend directly on specific SUT drivers or protocol implementations.
* **Enforcement:** Transport drivers must subclass `setve.adapters.base.TargetAdapter`. Interactions occur solely via async `read()`, `write()`, and `flush()` methods accepting `DirectBuffer` instances.

### 5. Dual-Indexed Documentation & End-to-End Traceability
* **Constraint:** All design documents, specifications, and architecture decisions must conform to the dual-indexed schema and taxonomy in [docs/DOCUMENTATION.md](file:///c:/dev/projects/simulate/docs/DOCUMENTATION.md).
* **Enforcement:**
  - Enforce YAML frontmatter schema (`id`, `type`, `status`, `domain`, `layer`, `c4_level`, `diataxis_type`, `traceability`, `code_references`).
  - Maintain the unbroken traceability DAG ($\text{BRD} \rightarrow \text{HLD} \rightarrow \text{ADR} \rightarrow \text{LLD} \rightarrow \text{Code/Test}$).
  - Before making code modifications, agents must inspect and update corresponding LLD/HLD/ADR documents in `docs/`.
  - When document IDs or filenames change (e.g. BRD renames), immediately update all cross-referencing ADR/HLD/LLD documents and re-run `python scripts/build_doc_graph.py`.

### 6. ADR-First LLD Authorship
* **Constraint:** ADRs define the non-negotiable constraints, trade-offs, and technology choices that LLDs must implement. No LLD may be authored before its governing ADRs are accepted.
* **Enforcement:**
  - Before drafting any LLD, agents must resolve all `governed_by_adr` references and load the full ADR context.
  - ADR guardrails (e.g., alignment rules, threading prohibitions, kernel version requirements) act as boundary enforcers — any LLD design that violates a governing ADR is invalid.
  - Directory numbering (`03-adr/` before `04-lld/`) reflects this dependency: decisions before implementation.

### 7. Anti-Drift Enforcement & Bi-Directional Traceability
* **Constraint:** Documentation must never drift from source code or tests.
* **Enforcement:** All code changes MUST be accompanied by updates to their referencing LLDs or ADRs. Ensure `code_references` and `test_references` in YAML frontmatter exactly match the actual paths modified.

### 8. Lifecycle & Deprecation Engine
* **Constraint:** Obsolete architectural patterns must not pollute RAG context.
* **Enforcement:** When an ADR or LLD is no longer valid, change its `status` frontmatter to `SUPERSEDED` or `DEPRECATED` rather than deleting it. The graph builder will automatically handle deprioritization.

### 9. Operational & Security Viewpoints
* **Constraint:** High-level designs must cover failure modes, blast radius, and security modeling.
* **Enforcement:** Use domains `operations` (for runbooks, chaos profiles, RTO/RPO) and `security` (for STRIDE threat models, memory-safety bounds) in document frontmatter when drafting operational or security specs.

---

## Coding Standards & Quality Gates

* **Python Version:** Python 3.12+
* **Type Safety:** 100% strict type coverage (`mypy --strict`). No untyped parameters or `Any` types in core modules.
* **Linter & Formatter:** `ruff` with standard PEP-8 adherence.
* **Error Handling:** Map raw OS errors (`errno`) to explicit `AdapterError` domains. System call failures must never be swallowed silently.
* **Performance Benchmark Threshold:** Core processing overhead (excluding SUT wait times) must not exceed $1\%$ of available CPU clock cycles per core.
* **Documentation Gate:** Code changes must be linked to active LLD/HLD specs via frontmatter `code_references`.

---

## Agent Task Execution Workflow

1. **Evaluate Request & Update Governance:** Parse incoming user prompt for behavioral feedback/preferences. If present, immediately update `AGENTS.md` rules first.
2. **Trace Context & Specs:** Query `docs/` using the frontmatter `traceability` graph ($\text{BRD} \rightarrow \text{HLD} \rightarrow \text{ADR} \rightarrow \text{LLD}$) to load exact requirements and design constraints before code generation.
3. **Classify Scope:** Identify whether task touches **Control Plane** (`orchestrator/`), **Data Plane** (`adapters/`, `payload/`), or **Validation Plane** (`validation/`).
4. **Hot Path Audit:** If modifying `adapters/` or `payload/`, verify zero dynamic allocations or data copying.
5. **Alignment Verification:** Validate $4096\text{-byte}$ page alignment on new buffer slicing operations.
6. **Type Check & Unit Test:** Run `mypy setve/` and `pytest tests/test_alignment.py`.
7. **Regression Verification:** Run `tests/benchmark_adapters.py` to confirm zero throughput degradation on hot paths.