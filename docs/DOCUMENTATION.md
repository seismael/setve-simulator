# Dual-Indexed Documentation Engine & Traceability Specification

## Overview & Architecture Framework

To maintain strict human engineering rigor while maximizing RAG retrieval precision and eliminating hallucinations for AI coding agents, SETVE synthesizes four industry documentation frameworks: **Arc42** (architectural structure), the **C4 Model** (hierarchical abstraction), **Diátaxis** (functional documentation types), and **IEEE 42010** (stakeholder view segregation), augmented with an **Agent-Native RAG Indexing Layer**.

This synthesis is known as the **Docs-as-Context (ContextOps)** framework. It represents the state of the art in agent-native software architecture, balancing engineering rigor with optimal Large Language Model (LLM) token efficiency to prevent context pollution and architectural drift.

### The 6 Pillars of the ContextOps Framework

| Pillar | Mechanism | Value for Humans & AI Agents |
| --- | --- | --- |
| **1. Strict Traceability** | $BRD \rightarrow HLD \rightarrow ADR \rightarrow LLD$ | Establishes a downward dependency chain so agents understand the *business intent* behind every line of code. |
| **2. Token Efficiency** | Single-responsibility modular files | Prevents context window saturation. Agents load only the specific $4096\text{-byte}$ aligned LLD or ADR relevant to their current task. |
| **3. Machine Indexing** | YAML Frontmatter + `.index/graph.json` | Replaces fuzzy semantic RAG search with deterministic graph traversal during agent context retrieval. |
| **4. Anti-Drift Enforcement** | CI/CD frontmatter and link checks | Fails builds if source code changes without an accompanying doc update, eliminating stale specification hallucinations. |
| **5. Automated Verification** | Hardware tests, eBPF probes, Mypy | Replaces agent self-judgment ("looks done") with concrete pass/fail feedback loops. |
| **6. Architectural Isolation** | Zero-copy hot loops (`O_DIRECT` / `io_uring`) | Decouples control-plane orchestrations from high-throughput data-plane execution. |

---

## 1. Architectural Framework Evaluation

| Framework | Core Strengths | Weaknesses for AI Agents | Adaptation for Dual-Indexing |
| --- | --- | --- | --- |
| **Arc42** | Deep technical structure; explicit quality tactics & runtime views. | Monolithic single-file structure degrades vector retrieval accuracy. | Deconstruct into modular, single-responsibility files by domain. |
| **C4 Model** | Strict hierarchical abstraction (Context $\rightarrow$ Container $\rightarrow$ Component $\rightarrow$ Code). | Lacks explicit business traceability (BRD) and decision governance. | Use C4 levels to drive directory taxonomy ($HLD \rightarrow LLD$). |
| **Diátaxis** | Clear segregation by user intent (Reference, Explanation, How-To, Tutorial). | Geared toward developer documentation, not system architecture lifecycle. | Map file suffixes to Diátaxis types to guide LLM prompt contexts. |
| **IEEE 42010** | Standardized viewpoint isolation (Security, Performance, Storage). | Overly bureaucratic for fast-moving engineering teams. | Map viewpoints directly to frontmatter `layer` and `domain` metadata. |

---

## 2. Directory Taxonomy & RAG Indexing Structure

Documents are partitioned into deterministic, single-responsibility files to guarantee vector embeddings map to unpolluted semantic spaces.

```text
docs/
├── .index/
│   ├── graph.json              # Full dependency DAG (BRD -> HLD -> ADR -> LLD -> Code)
│   └── taxonomy.schema.json    # Strict JSON Schema for YAML frontmatter
├── 01-brd/                     # Business & System Requirements (What & Why)
│   └── <domain>/<id>-brd.md
├── 02-hld/                     # C1/C2 System Topology & Component Abstraction (Where & Boundaries)
│   └── <domain>/<id>-hld.md
├── 03-adr/                     # Architectural Decision Records (Which & Guardrails)
│   └── NNNN-<title>.md
└── 04-lld/                     # C3/C4 Memory Layouts, APIs, Class/Module Specs (How & Concrete Code)
    └── <layer>/<id>-lld.md
```

---

## 3. Production-Grade Template Suite

### A. Universal Agent-Native Metadata Schema (YAML Frontmatter)

Every document in the repository **must** include this header to enable deterministic graph traversal by AI agents.

```yaml
---
id: "HLD-DATA-001"             # Unique global identifier: [TYPE]-[DOMAIN]-[INDEX]
title: "Zero-Copy SIMD Memory Generation Engine"
type: "HLD"                     # [BRD | HLD | LLD | ADR]
status: "APPROVED"              # [DRAFT | PROPOSED | APPROVED | SUPERSEDED | DEPRECATED]
domain: "data-plane"            # [control-plane | data-plane | observability | validation | operations | security]
layer: "compute-engine"         # [ingress | compute-engine | storage | transport | telemetry]
c4_level: "container"           # [context | container | component | code]
diataxis_type: "explanation"    # [reference | explanation | how-to | tutorial]
traceability:
  implements_brd: ["BRD-PERF-001", "BRD-SCALE-002"]
  governed_by_adr: ["ADR-0003", "ADR-0007"]
  parent_hld: null
  child_llds: ["LLD-SIMD-001", "LLD-RING-002"]
code_references:
  - "setve/payload/mutator.py"
  - "setve/payload/buffer_pool.py"
test_references:
  - "tests/test_mutator.py"
owner: "@architecture-team"
last_validated_date: "2026-08-05"
---
```

---

### B. Business Requirements Document (BRD) Template

```markdown
# BRD-[DOMAIN]-[INDEX]: [Feature / Initiative Title]

## 1. Executive Summary & Business Drivers
* **Problem Statement:** Concise, quantifiable description of the bottleneck or operational gap.
* **Business Outcome:** Target capabilities (e.g., enable $\ge 8\text{ GB/s}$ load simulation per node to validate infrastructure limits).
* **Target Stakeholders:** System architects, performance engineers, platform teams.

## 2. Functional & Non-Functional Requirements Matrix

| Req ID | Category | Requirement Description | Target Metric / Constraint | Priority | Verification Method |
|---|---|---|---|---|---|
| BRD-PERF-01 | Non-Func | Continuous Throughput | $\ge 8\text{ GB/s}$ sustained per node | P0 | Automated Load Test |
| BRD-SCALE-02 | Functional | Multi-Protocol Target Support | POSIX Direct I/O, S3, io_uring | P0 | Integration Test Suite |
| BRD-OBS-03 | Non-Func | Telemetry Accuracy | $\le 0.1\%$ divergence vs HW | P1 | eBPF Counter Audit |

## 3. System Constraints & Operating Assumptions
* **Hardware Assumptions:** PCIe Gen4/Gen5 buses, minimum 100GbE NICs, Linux Kernel $\ge 5.10$.
* **Out-of-Scope:** Proprietary, non-standard vendor APIs without public interface bindings.
```

---

### C. High-Level Design (HLD) Template

```markdown
# HLD-[DOMAIN]-[INDEX]: [System / Component Name]

## 1. System Context & C4 Architecture (Levels 1 & 2)
* **System Boundary:** High-level topology diagram illustrating inputs, compute layers, and SUT interfaces.
* **Component Responsibilities:**
  * `Orchestrator`: Controls core affinity and process distribution.
  * `Payload Generator`: Handles SIMD-accelerated memory mutation.
  * `Target Adapter`: Manages asynchronous non-blocking kernel passes.

## 2. Data Flow & Interface Contracts

```
[ Ingestion API ] ──(Direct Memory)──> [ Pre-Allocated Ring Buffer ]
│
(In-Place SIMD Mutation)
│
▼
[ SUT Endpoint ] <──(io_uring SQE)─── [ Direct IO Adapter ]
```

## 3. Cross-Cutting Engineering Concerns

| Concern | Strategy | Architectural Mechanism | Related ADR |
|---|---|---|---|
| **Memory Isolation** | Zero dynamic heap allocation | Anonymous `mmap` page-aligned buffers | ADR-0002 |
| **Concurrency** | CPU core affinity pinning | Single-threaded `uvloop` per process | ADR-0004 |
| **Observability** | Out-of-band tracing | eBPF kernel event probes + ClickHouse | HLD-OBS-001 |
```

---

### D. Architecture Decision Record (ADR) Template

> **ADRs precede LLDs.** ADRs define the non-negotiable constraints and technology
> choices that LLDs must implement. An LLD cannot be validly authored without first
> binding to the ADRs that govern it.

```markdown
# ADR-NNNN: [Imperative Action Title, e.g., Adopt io_uring for Storage Subsystems]

## Context & Problem Statement
High-throughput storage simulation in Python suffers from kernel context-switching overhead and GIL locks when executing synchronous `pread/pwrite` system calls.

## Evaluated Alternatives

| Alternative | Throughput Capability | CPU Overhead | Kernel Requirement |
|---|---|---|---|
| **1. Multi-threaded POSIX Direct I/O** | $2.1\text{ GB/s}$ | High (GIL contention) | Any POSIX |
| **2. Asyncio + uvloop Process Pool** | $4.8\text{ GB/s}$ | Medium | Linux $\ge 4.18$ |
| **3. Linux io_uring (liburing)** | $\ge 8.0\text{ GB/s}$ | Low (Zero syscall mode) | Linux $\ge 5.10$ |

## Decision & Justification
**Selected Option:** Option 3 (`io_uring`).
**Rationale:** Submits batch requests directly to kernel submission rings without system call overhead per operation, fulfilling **BRD-PERF-01**.

## Trade-offs & Consequences
* **Positive:** Achieves native line-rate throughput in Python workers.
* **Negative:** Drops support for non-Linux host environments (macOS/Windows restricted to mock drivers).
```

---

### E. Low-Level Design (LLD) Template

> **LLDs are governed by ADRs.** Every LLD must declare `governed_by_adr` in its
> frontmatter and comply with the constraints established by those ADRs.

```markdown
# LLD-[LAYER]-[INDEX]: [Specific Module / Subsystem Name]

## 1. Concrete Module & Class Architecture (C4 Level 3 & 4)
* **Target Package:** `setve.payload.mutator`
* **Interface Specification:**
  * Input: `DirectBuffer` (Must satisfy `address % 4096 == 0`)
  * Execution: AVX-512 register streaming via C-extension/NumPy bindings.

## 2. Low-Level Memory Layout & Vectorization Logic

```
64-Byte Cache Line
┌──────────────────────────────────────────────────────────────┐
│ Byte 0                            ...                Byte 63 │
├──────────────────────────────────────────────────────────────┤
│                AVX-512 Vector Register (_mm512)              │
└──────────────────────────────────────────────────────────────┘
```

* **Alignment Safeguard:**
```python
def assert_buffer_alignment(buf: DirectBuffer, alignment: int = 4096) -> None:
    if buf.address % alignment != 0:
        raise AlignmentError(f"Buffer at {hex(buf.address)} violates {alignment}-byte boundary")
```

## 3. Error Recovery & Exception State Machine
* **Queue Full (`EBUSY`):** Drain Completion Queue Events (CQEs) and yield event loop execution.
* **Buffer Misalignment (`EINVAL`):** Hard fail process instantly; log alignment violation stack trace.
```

---

## 4. End-to-End Document Traceability Graph

To ensure deterministic navigation for developers and AI agents, every requirement must flow downwards through an unbroken chain:

$$\text{BRD (Requirement)} \longrightarrow \text{HLD (Architecture)} \longrightarrow \text{ADR (Decision)} \longrightarrow \text{LLD (Implementation)} \longrightarrow \text{Code / Unit Test}$$

1. **RAG Search Strategy:** When an agent answers a query, it reads the document's `traceability` block to recursively fetch parent context (BRD) or child specs (LLD) before generating code.
2. **Validation Gate:** A pre-commit hook parses `.index/graph.json` to verify that no orphan LLDs exist without an approving HLD, and no HLD violates an ADR.