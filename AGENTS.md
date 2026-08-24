# AGENTS.md: Storage, Telemetry, Engine, Verification, and Evaluation (STEVE)

## Dynamic Governance & Self-Evolution Protocol

> **MANDATORY PRE-EXECUTION STEP:** On **EVERY** user request, agents MUST first perform a behavioral evaluation pass.

1. **Evaluate Behavioral Signals:** Analyze user requests for feedback, complaints, operational preferences, architectural corrections, test generation rules, or workflow expectations.
2. **Dynamic Governance Update:** If any actionable behavioral guideline or constraint is identified (e.g., test structure preferences, directory layout changes, code style adjustments, documentation rules, or requirement ID updates), **immediately edit `AGENTS.md`** to permanently codify the new rule under Technical Guardrails or Coding Standards **BEFORE** executing the task.
3. **Consistent Enforcement:** All future steps and agent sessions MUST strictly enforce the dynamically updated rules in `AGENTS.md`.

---

## Project Vision & System Context
**STEVE** (Storage, Telemetry, Engine, Verification, and Evaluation) is a platform-agnostic, multi-gigabyte-per-second load generation and telemetry verification engine engineered to stress-test high-performance storage and data-plane systems from single nodes to multi-TB/s clusters across NVMe-oF, POSIX Direct I/O, S3 object stores, vector databases, and AI prefill/decode pipelines.

Primary runtime: **Python 3.12+**.
For detailed technical design and implementation blueprints, refer to [SPEC.md](file:///c:/dev/projects/setve-simulator/SPEC.md) and [docs/DOCUMENTATION.md](file:///c:/dev/projects/setve-simulator/docs/DOCUMENTATION.md).

---

## Directory & Package Layout

```
steve/
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

deploy/                        # 3-Tier Enterprise Deployment & Infrastructure Ecosystem
├── packaging/                 # Immutable build definitions (docker, helm, operator)
├── environments/              # Target environment overlays (local, dev, staging, prod)
└── emulator/                  # Local multi-node distributed cluster simulator & gRPC sync
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
* **Enforcement:** Transport drivers must subclass `steve.adapters.base.TargetAdapter`. Interactions occur solely via async `read()`, `write()`, and `flush()` methods accepting `DirectBuffer` instances.

### 5. Dual-Indexed Documentation & End-to-End Traceability
* **Constraint:** All design documents, specifications, and architecture decisions must conform to the dual-indexed schema and taxonomy in [docs/DOCUMENTATION.md](file:///c:/dev/projects/setve-simulator/docs/DOCUMENTATION.md).
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

### 10. Agentic Documentation Updates (ADX Efficiency)
* **Constraint:** Agents must independently maintain the `.index/graph.json` state.
* **Enforcement:** When creating, moving, or updating the frontmatter of any `.md` file in `docs/`, you MUST immediately execute `python scripts/build_doc_graph.py` to regenerate the graph before finalizing your task. This ensures the RAG index remains perfectly accurate for the next agent session.

### 11. LLM Cost Efficiency & Implementation Quality
* **Constraint:** AI Agents must strictly minimize their token footprint (cost) while maximizing the accuracy of architectural implementations.
* **Enforcement:**
  - **Efficiency:** Never bulk-read directories or sequential markdown files. By isolating reads to exact `code_references:` and `graph.json` traversal, the agent dramatically drops input tokens, driving down API costs and preventing context saturation.
  - **Quality Implementation:** Semantic guessing is banned. Agents must extract exact constraints (e.g., $4096\text{-byte}$ alignment) directly from the target LLD before writing code, ensuring the implementation output is deterministic, professional, and mathematically validated by the test suite.

### 12. Unified Exception Hierarchy & Zero-Allocation Structured Logging
* **Constraint:** System faults must never raise raw, generic Python exceptions (`Exception`, `ValueError`, `OSError`) without explicit domain context. Logging must never block or allocate dynamically on I/O hot paths.
* **Enforcement:**
  - Map all OS `errno` codes to granular `SteveError` subclasses (`MisalignedOffsetError`, `HardwareIoError`, `StorageExhaustedError`, `ConnectionTimeoutError`).
  - Hot paths must use asynchronous or queue-based structured loggers with log-level gating, ensuring zero string interpolation overhead during active I/O loops.

### 13. 3-Tier Enterprise Deployment Governance (`deploy/`)
* **Constraint:** All deployment configurations, infrastructure manifests, container definitions, Helm charts, Kubernetes operators, multi-node cluster runners, and environment definitions must reside exclusively in the canonical 3-tier `deploy/` directory structure. Ad-hoc or duplicate deployment folders are strictly forbidden.
* **Enforcement:**
  - `deploy/packaging/`: Build definitions (`docker/` multi-stage Dockerfile, `helm/` production charts, `operator/` Kopf operator & CRDs).
  - `deploy/environments/`: Target environment overlays (`local/` developer compose & Grafana stack, `dev/` terraform, `staging/`, `prod/`).
  - `deploy/emulator/`: Local multi-node cluster simulator and gRPC barrier synchronization runner (`cluster_runner.py`).
  - All test files, validation scripts, and documentation must reference paths under `deploy/packaging/`, `deploy/environments/`, or `deploy/emulator/`.

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
2. **Trace Context & Specs (ADX Efficient Navigation):** Do NOT read `docs/` sequentially. Use `grep_search` on the `docs/` directory to locate specific `domain:`, `id:`, or `code_references:` matches (e.g., search for `steve/payload/mutator.py` to find its governing LLD). Use `view_file` on `.index/graph.json` to instantly map dependencies ($\text{BRD} \rightarrow \text{HLD} \rightarrow \text{ADR} \rightarrow \text{LLD}$) without wasting tokens on full file reads. Keep your context window tight.
3. **Classify Scope:** Identify whether task touches **Control Plane** (`orchestrator/`), **Data Plane** (`adapters/`, `payload/`), or **Validation Plane** (`validation/`).
4. **Hot Path Audit:** If modifying `adapters/` or `payload/`, verify zero dynamic allocations or data copying.
5. **Alignment Verification:** Validate $4096\text{-byte}$ page alignment on new buffer slicing operations.
6. **Type Check & Unit Test:** Run `mypy steve/` and `pytest tests/test_alignment.py`.
7. **Regression Verification:** Run `tests/benchmark_adapters.py` to confirm zero throughput degradation on hot paths.