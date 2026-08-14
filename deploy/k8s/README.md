# SETVE Kubernetes Operator Guide

The SETVE Kubernetes Operator provides declarative lifecycle management for multi-node storage and data-plane load generation clusters.

---

## Operator Architecture

```text
  ┌────────────────────────────────────────────────────────────┐
  │                 Kubernetes API Server                      │
  │        CustomResourceDefinition: SETVECluster              │
  └─────────────────────────────┬──────────────────────────────┘
                                │ Watch & Reconcile
                                ▼
  ┌────────────────────────────────────────────────────────────┐
  │                 SETVE Kopf Operator Controller             │
  │   - Computes deterministic worker shard offsets            │
  │   - Deploys core-pinned Worker Pods via StatefulSet        │
  │   - Creates KEDA ScaledObject for dynamic throughput       │
  │   - Exposes Prometheus ServiceMonitor endpoints            │
  └────────────────────────────────────────────────────────────┘
```

---

## Custom Resource Definition (`SETVECluster`)

```yaml
apiVersion: setve.io/v1alpha1
kind: SETVECluster
metadata:
  name: nvme-bench-01
  namespace: setve-system
spec:
  nodeCount: 4
  coresPerNode: 8
  targetThroughputGbps: 80.0
  targetUri: "posix:///mnt/nvme/target.dat"
  blockSizeBytes: 1048576
  entropyRatio: 0.75
  durationSeconds: 30
  telemetry:
    port: 8000
    prometheusExport: true
```

---

## Running the Operator

```bash
# Run locally against active kubeconfig context
python deploy/k8s/operator/controller.py --standalone

# Or deploy into cluster as Deployment
kubectl apply -f deploy/k8s/operator/
```
