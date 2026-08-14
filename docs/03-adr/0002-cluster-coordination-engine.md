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

## Context & Problem Statement
To coordinate a fleet of compute workers executing high-throughput I/O tests, the master control plane needs a synchronization mechanism for barrier signals and target slice assignments, avoiding single-point lock contention.

## Evaluated Alternatives
1. **NATS JetStream:** High performance, pub/sub model. Requires external infrastructure.
2. **etcd:** Strong consistency, standard in k8s. Heavy overhead for simple barrier sync.
3. **Custom gRPC (Selected):** Direct master-worker communication. No external dependencies, natively supports barrier synchronization.

## Decision & Justification
**Selected Option:** Custom gRPC.
**Rationale:** A masterless/gRPC coordination model provides no single-point lock during execution loops and avoids external dependencies, facilitating ephemeral CI/CD test clusters. Container privilege bounds (CAP_SYS_ADMIN, Host IPC) will be enforced for worker containers to access io_uring and SR-IOV networks.

## Trade-offs & Consequences
* **Positive:** Minimal deployment footprint, zero external broker latency.
* **Negative:** Requires custom implementation of partition reassignment if a node drops.
