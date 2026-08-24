---
id: "HLD-K8S-001"
title: "Kubernetes Operator, KEDA Auto-Scaling, & Pod Topology Infrastructure"
type: "HLD"
status: "APPROVED"
domain: "infrastructure"
layer: "ingress"
c4_level: "container"
diataxis_type: "explanation"
traceability:
  implements_brd: ["BRD-STEVE-001", "BRD-DIST-001"]
  governed_by_adr: ["ADR-0001", "ADR-0002"]
  parent_hld: "HLD-DIST-001"
  child_llds: ["LLD-K8S-001"]
code_references:
  - "deploy/packaging/operator/controller.py"
  - "deploy/packaging/helm/steve-cluster/values.yaml"
test_references:
  - "tests/test_blueprint.py"
owner: "@architecture-team"
last_validated_date: "2026-08-05"
---


# HLD-K8S-001: Kubernetes Operator, KEDA Auto-Scaling, & Pod Topology Infrastructure

## 1. Infrastructure Scope & Kubernetes Architecture

HLD-K8S-001 defines the cloud-native deployment model for scaling STEVE compute fleets across Kubernetes infrastructure. It encapsulates worker pod scheduling, hardware resource isolation, host kernel privileges (`CAP_SYS_ADMIN`), and dynamic scale-out triggers using the Kubernetes Event-driven Autoscaling (KEDA) framework.

```text
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           KUBERNETES CONTROL PLANE                              │
│   ┌────────────────────────────────┐       ┌─────────────────────────────────┐  │
│   │ STEVE Operator (Custom CRD)    │──────►│ KEDA ScaledObject Controller    │  │
│   └────────────────────────────────┘       └─────────────────────────────────┘  │
└──────────────────────────────────────┬──────────────────────────────────────────┘
│ Reconciles Pod Deployments
┌───────────────────────────────┴───────────────────────────────┐
▼                                                               ▼
┌──────────────────────────────────────────────┐┌──────────────────────────────────────────────┐
│       NODE POOL A (NUMA Socket 0)            ││       NODE POOL B (NUMA Socket 1)            │
│ ┌──────────────────────────────────────────┐ ││ ┌──────────────────────────────────────────┐ │
│ │ Worker Pod (Host IPC, CAP_SYS_ADMIN)     │ ││ │ Worker Pod (Host IPC, CAP_SYS_ADMIN)     │ │
│ │ ├── io_uring Kernel Ring                 │ ││ │ ├── io_uring Kernel Ring                 │ │
│ │ ├── Page-Aligned Anonymous mmap          │ ││ │ ├── Page-Aligned Anonymous mmap          │ │
│ │ └── SR-IOV Physical Interface            │ ││ │ └── SR-IOV Physical Interface            │ │
│ └──────────────────────────────────────────┘ ││ └──────────────────────────────────────────┘ │
└──────────────────────────────────────────────┘└──────────────────────────────────────────────┘
```

---

## 2. Custom Resource Definition (CRD) Architecture

The `STEVECluster` Custom Resource Definition exposes declarative workload properties directly to platform operations and AI orchestrators.

```yaml
apiVersion: steve.io/v1alpha1
kind: STEVECluster
metadata:
  name: steve-production-bench
  namespace: steve-system
spec:
  targetEndpoint: "nvmeof://10.240.0.50:4420"
  targetThroughputGbps: 800
  blockSizeBytes: 1048576
  entropyRatio: 0.85
  syncTimeoutSeconds: 30
  workloadDurationSeconds: 300
  nodeSelector:
    steve.io/performance-tier: "baremetal-gpu-storage"
  resourcesPerWorker:
    cpuCores: 16
    memoryHugePagesGiB: 32
  scalingPolicy:
    minReplicas: 4
    maxReplicas: 128
    targetQueueLag: 50
```

---

## 3. Pod Topology & Hardware Security Boundary

To achieve zero-copy line-rate throughput without kernel contention, STEVE pods require elevated node privileges and non-overlapping topology constraints:

* **Host IPC & Pid Namespaces (`hostIPC: true`):** Permits zero-copy shared memory access across multi-process core workers.
* **Kernel Capabilities (`CAP_SYS_ADMIN`):** Required for locked memory allocations (`mlock`), `io_uring_setup`, and direct kernel memory bypass.
* **Pod Anti-Affinity:** Prevents multiple worker pods from competing for the same physical PCIe bus lanes or NUMA memory nodes.
