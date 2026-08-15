---
id: "HLD-ENV-001"
title: "Multi-Tier Infrastructure & Environment Lifecycle Architecture"
type: "HLD"
status: "APPROVED"
domain: "infrastructure"
layer: "ingress"
c4_level: "container"
diataxis_type: "explanation"
traceability:
  implements_brd: ["BRD-SETVE-001", "BRD-DIST-001"]
  governed_by_adr: ["ADR-0001", "ADR-0002"]
  parent_hld: "HLD-SETVE-001"
  child_llds: []
code_references:
  - "deploy/environments/local/prometheus.yml"
test_references:
  - "tests/test_reporter.py"
owner: "@architecture-team"
last_validated_date: "2026-08-05"
---


# HLD-ENV-001: Multi-Tier Infrastructure & Environment Lifecycle Architecture

## 1. Executive Summary & Environment Taxonomy

This document establishes the official 4-tier environment deployment matrix for SETVE. Because SETVE depends on low-level Linux kernel features (`io_uring`, `O_DIRECT`, eBPF probes, `CAP_SYS_ADMIN`, and NUMA core pinning), standard application environments are insufficient. 

The environment topology provides developer agility on local workstations while guaranteeing hardware-accurate performance validation across remote sandboxes, staging clusters, and production releases.

| Environment Tier | Target Host / Hardware | Target Capability | Deployment Trigger | Primary Purpose |
|---|---|---|---|---|
| **Local (Workstation)** | Laptop / IDE (macOS, Linux, WSL2) | Mock / Software Drivers (`PosixDirectIOAdapter`) | Developer `git commit` | Fast inner-loop iteration; syntax, unit testing, and mock adapter logic. |
| **Dev (Remote Sandbox)** | Ephemeral Single-Node Linux Bare-Metal | Native `io_uring`, `O_DIRECT`, `CAP_SYS_ADMIN` | `git push` to developer branch | Core-pinned hot-path development, eBPF probe testing, zero-copy benchmarking. |
| **Staging (Shared Cluster)** | Multi-Node K8s / Bare-Metal Fleet | Multi-node gRPC barrier sync, KEDA, eBPF telemetry | Merge PR into `staging` branch | Continuous integration, baseline performance regression gates, dynamic load scale tests. |
| **Production (Release Target)** | Hardened Hyperscale Bare-Metal / K8s | Unlimited scale ($\ge 800\text{ Gbps}$ / multi-TB/s) | Version tag / Merge into `main` | Official infrastructure benchmarking, customer SUT capacity validation, release engine. |

---

## 2. Environment Layer Specifications

### 2.1 Local Environment (Developer Workstation)
* **Goal:** Sub-second inner-loop feedback for writing business logic, unit tests, and driver interfaces without requiring a Linux kernel with `io_uring` or root access.
* **Architecture:**
  * Uses a fallback mock driver (`PosixDirectIOAdapter`) or standard socket emulation when native `io_uring` kernel headers are absent.
  * Local containerized dependencies (SETVE, MinIO, Prometheus, Grafana) managed via `deploy/environments/local/docker-compose.yml`.
* **Resource Bounds:** 2 to 4 CPU cores, mock storage directories, loopback network (`127.0.0.1`).

### 2.2 Dev Environment (Remote Developer Sandbox)
* **Goal:** Enable engineers to validate kernel-level code (`io_uring` ring sizes, SIMD AVX-512 vectorization, eBPF event probes) on dedicated, remote hardware without polluting shared environments.
* **Architecture:**
  * Ephemeral single-node Linux server (bare-metal or AWS `c6i.metal` / GCP bare-metal instance) provisioned on-demand via `make dev-up` (Terraform + Ansible).
  * Direct access to physical NVMe storage (`O_DIRECT`), Linux Kernel $\ge 5.10$, and user-space memory lock privileges (`ulimit -l unlimited`).
* **Deployment Mechanism:** Developer branch pushed via SSH / rsync or container image push to dev container registry.

### 2.3 Staging Environment (Shared Integration & Scale Cluster)
* **Goal:** Automated verification of multi-node gRPC barrier synchronization, metric triangulation accuracy ($\le 0.1\%$ skew), and KEDA auto-scaling limits under simulated SUT workloads.
* **Architecture:**
  * Multi-node Kubernetes cluster (3 to 16 physical worker nodes) equipped with SR-IOV network interfaces and out-of-band ClickHouse telemetry ingestion.
  * Automatically receives deployment updates upon every successful Pull Request merge into the `staging` git branch via GitOps (ArgoCD / Flux).
* **Automated Quality Gate:** A nightly 30-minute stress run executes automatically. If throughput drops $> 2\%$ below baseline or eBPF metric skew exceeds $0.1\%$, the staging pipeline blocks promotion to production.

### 2.4 Production Environment (Release & Customer Benchmark Engine)
* **Goal:** Execute production-grade benchmark scenarios against real-world customer storage infrastructure and internal high-performance data planes.
* **Architecture:**
  * Bare-metal multi-rack Kubernetes cluster or dedicated high-throughput compute topology (16 to 1,024+ nodes).
  * Strict physical isolation between the data plane (100GbE / 800GbE network fabrics) and control/telemetry management interfaces.
* **Deployment Mechanism:** Immutable Helm releases triggered by git release tags (e.g., `v1.2.0`) merged into the `main` branch.

---

## 3. Kernel & Hardware Capability Matrix

Because SETVE targets bare-metal execution parameters, each environment tier exposes specific hardware interfaces:

```text
[ Local (Laptop) ]       ──► Fallback Driver  ──► Mock Sockets / POSIX File Handles
[ Dev (Remote Box) ]     ──► io_uring Driver  ──► O_DIRECT / eBPF Probes / Core Pinning
[ Staging Cluster ]      ──► gRPC Sync Fleet  ──► Multi-Node KEDA / eBPF Triangulation
[ Production Fabric ]    ──► Hyperscale Fleet ──► SR-IOV / 800GbE Fabric / Line-Rate Target
```

| Feature / Interface | Local | Dev Sandbox | Staging | Production |
|---|---|---|---|---|
| **OS Host** | macOS / Win / Linux | Linux Kernel $\ge 5.10$ | Linux Kernel $\ge 5.10$ | Linux Kernel $\ge 5.10$ |
| **`io_uring` Support** | Mock / Emulated | **Native Enabled** | **Native Enabled** | **Native Enabled** |
| **Direct I/O (`O_DIRECT`)** | Disabled (Buffer Copy) | **Enabled** | **Enabled** | **Enabled** |
| **SIMD AVX-512 Vectoring** | Optional (Emulated) | **Enabled** | **Enabled** | **Enabled** |
| **CPU Core Affinity Pinning** | Disabled | **Enabled** | **Enabled** | **Enabled** |
| **eBPF Kernel Probes** | Disabled | **Enabled** | **Enabled** | **Enabled** |
| **Multi-Node gRPC Barrier** | Local Mock | Single-Node Mock | **Multi-Node Cluster** | **Hyperscale Cluster** |

---

## 4. GitOps Promotion & Environment Lifecycle Pipeline

```text
[ Feature Branch ]
│
├── (Push code / PR creation)
▼

1. Local & Dev Checks ──────► Runs Linters, Mypy Strict, Unit Tests
│
├── (Merge PR into `staging` branch)
▼
2. Staging Environment ─────► ArgoCD Deploys to Staging Cluster
│                      ├── Runs Multi-Node Integration Tests
│                      └── Runs Performance Regression Benchmark
│
├── (Performance Verification Passes & Tag Created)
▼
3. Production Release ──────► Helm Chart Deployed to Production Fleet
└── Executes Scheduled Infrastructure Runs
```

1. **Inner Loop (Local $\rightarrow$ Dev):** Developer writes code locally, verifying logic via unit tests. Developer pushes branch to trigger ephemeral remote Dev Sandbox provisioning for `io_uring` and eBPF kernel validation.
2. **PR Merge (Dev $\rightarrow$ Staging):** Pull Request approved and merged into `staging`. CI pipeline builds immutable OCI container image, updates Staging Helm values, and ArgoCD syncs the Staging cluster. Automated regression tests evaluate throughput and metric divergence.
3. **Release Tag (Staging $\rightarrow$ Production):** After passing staging regression gates, a release version tag (`vX.Y.Z`) is pushed to `main`. ArgoCD syncs the production release chart to the production execution cluster.

---

## 5. Security Isolation & Environment Guardrails

* **Privilege Boundaries:** `CAP_SYS_ADMIN` privileges required for `io_uring` and eBPF are restricted to worker pod security contexts using Kubernetes Pod Security Admission (`PSA: privileged`) scoped strictly to `setve-system` namespaces.
* **Network Partitioning:** Staging and Dev environments operate on isolated VLANs/subnets to prevent synthetic traffic generation from leaking into internal corporate networks or production SUT endpoints.
* **Data Sanitization:** Local and Dev environments use synthetic random data generators (`PySIMDPayloadMutator`) exclusively; no production telemetry or customer configuration schemas are stored in non-production environments.
