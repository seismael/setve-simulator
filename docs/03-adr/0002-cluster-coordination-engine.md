---
id: "ADR-0002"
title: "Select Cluster Coordination Engine and Privilege Boundaries"
type: "ADR"
status: "APPROVED"
domain: "control-plane"
layer: "compute-engine"
c4_level: "component"
diataxis_type: "explanation"
traceability:
  implements_brd: ["BRD-DIST-001"]
  governed_by_adr: []
  parent_hld: "HLD-DIST-001"
  child_llds: ["LLD-ORCH-001"]
code_references:
  - "setve/orchestrator/sync.py"
  - "setve/orchestrator/cluster.py"
test_references:
  - "tests/test_cluster_sync.py"
  - "tests/test_sharding.py"
owner: "@architecture-team"
last_validated_date: "2026-08-05"
---

# ADR-0002: Select Cluster Coordination Engine and Privilege Boundaries

## 1. Context & Problem Statement
To coordinate a fleet of distributed compute workers executing high-throughput I/O tests against storage data planes ($\ge 1\text{ TB/s}$ cluster aggregate), the orchestration plane requires a synchronization mechanism for barrier signals and target slice assignments without introducing runtime lock contention.

---

## 2. Evaluated Alternatives

1. **NATS JetStream:** High performance, pub/sub model. Requires deploying and maintaining external broker clusters.
2. **etcd / ZooKeeper:** Strong consistency, standard in Kubernetes. High latency and heavy resource overhead for high-frequency barrier handshakes.
3. **Shared-Nothing SplitMix64 + Custom gRPC Barrier (Selected):** Direct master-worker gRPC communication for 3-phase synchronization with local mathematical shard computation.

---

## 3. Decision & Justification
**Selected Option:** Shared-Nothing SplitMix64 Deterministic Sharding + Custom gRPC Barrier Synchronization.

### Rationale:
* **Zero Hot-Path Inter-Node Traffic:** Deterministic SplitMix64 mathematical hash calculations eliminate runtime master queries for block offsets.
* **Nanosecond Barrier Alignment:** 3-phase gRPC handshake (`SIGNAL_READY`, `BARRIER_RELEASE`, `SIGNAL_COMPLETED`) guarantees synchronized load release without startup skew.
* **Minimal Footprint:** Runs independently in bare-metal, containerized, and local emulation environments without external message brokers.
* **Privilege Bounds:** Worker containers enforce `CAP_SYS_ADMIN` and Host IPC bounds to access physical NVMe Direct I/O and `io_uring` kernel rings.

---

## 4. Trade-offs & Consequences
* **Positive:** Linearly scalable ($\mathcal{O}(N)$), zero broker latency, lightweight CI/CD integration.
* **Negative:** Node drop events require deterministic recalculation of active shard intervals by the master orchestrator.
