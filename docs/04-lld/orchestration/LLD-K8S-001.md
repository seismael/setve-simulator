---
id: "LLD-K8S-001"
title: "Kubernetes Operator & KEDA Binding Implementations"
type: "LLD"
status: "APPROVED"
domain: "infrastructure"
layer: "ingress"
c4_level: "code"
diataxis_type: "reference"
traceability:
  implements_brd: ["BRD-STEVE-001", "BRD-DIST-001"]
  governed_by_adr: ["ADR-0002"]
  parent_hld: "HLD-K8S-001"
  child_llds: []
code_references:
  - "deploy/packaging/operator/controller.py"
  - "deploy/packaging/helm/steve-cluster/values.yaml"
  - "deploy/packaging/operator/crds/stevecluster-crd.yaml"
test_references:
  - "tests/test_deploy.py"
  - "tests/test_blueprint.py"
owner: "@architecture-team"
last_validated_date: "2026-08-05"
---

# LLD-K8S-001: Kubernetes Operator & KEDA Binding Implementations

## 1. Operator Architecture & CRD Reconciliation

`LLD-K8S-001` specifies the `STEVECluster` reconcile logic. The Python-based Kopf operator responds to CRD modifications (`steve.io/v1alpha1`), translating declarative throughput and node specs into scalable Kubernetes resources managed by KEDA.

```text
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    KUBERNETES OPERATOR HORIZONTAL SCALE-OUT                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   ┌───────────────────────────┐                ┌────────────────────────────┐   │
│   │ STEVECluster CRD Spec     │ ─────────────> │ Kopf Operator Controller   │   │
│   │ (nodeCount: 16, 200 Gbps) │                │ (deploy/packaging/operator)│   │
│   └───────────────────────────┘                └─────────────┬──────────────┘   │
│                                                              │                  │
│                        ┌─────────────────────────────────────┴──────────────┐   │
│                        ▼                                                    ▼   │
│   ┌──────────────────────────────────────────┐   ┌──────────────────────────┐   │
│   │ Master Deployment (gRPC Port 50051)      │   │ Worker DaemonSet / Fleet │   │
│   │ (Deterministic Shard & Sync Servicer)    │   │ (Core-Pinned uvloop Pods)│   │
│   └──────────────────────────────────────────┘   └───────────┬──────────────┘   │
│                                                              │                  │
│                                                              ▼                  │
│                                                  ┌──────────────────────────┐   │
│                                                  │ KEDA ScaledObject        │   │
│                                                  │ (Scales 1 -> 64 Replicas)│   │
│                                                  └──────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Operator Controller Logic (`deploy/packaging/operator/controller.py`)

```python
"""Kubernetes Operator for STEVECluster CRD Lifecycle."""

import kopf


@kopf.on.create("steve.io", "v1alpha1", "steveclusters")
def create_fn(spec: dict, name: str, namespace: str, logger: kopf.Logger, **kwargs: dict) -> dict:
    logger.info(f"Reconciling STEVECluster: {name} in {namespace}")

    node_count = spec.get("nodeCount", 2)
    cores_per_node = spec.get("coresPerNode", 4)
    target_throughput_gbps = spec.get("targetThroughputGbps", 10.0)

    # 1. Provision Master Orchestrator Deployment & ClusterIP Service
    # 2. Provision Worker DaemonSet with SR-IOV and host-level Direct I/O mounts
    # 3. Provision KEDA ScaledObject for auto-scaling worker fleet
    return {
        "status": "Ready",
        "cluster_nodes": node_count,
        "total_cores": node_count * cores_per_node,
        "target_throughput_gbps": target_throughput_gbps,
    }
```
