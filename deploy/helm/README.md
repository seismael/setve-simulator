# SETVE Helm Chart Guide

The `setve-cluster` Helm chart deploys the SETVE distributed load generation and telemetry verification engine to Kubernetes clusters.

---

## Prerequisites

- Kubernetes cluster $\ge 1.26$
- Helm $\ge 3.8.0$
- Node feature discovery / CPU Manager enabled for core pinning (`cpuset`)

---

## Installation

```bash
# 1. Add repository or use local chart
cd deploy/helm/setve-cluster

# 2. Dry-run and template inspection
helm template setve-cluster . -f values.yaml

# 3. Install release
helm install setve-cluster . \
  --namespace setve-system \
  --create-namespace \
  --values values.yaml
```

---

## Configuration Reference (`values.yaml`)

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `cluster.name` | `string` | `"setve-cluster"` | Cluster identifier |
| `cluster.nodeCount` | `int` | `8` | Number of worker pods across nodes |
| `cluster.coresPerNode` | `int` | `8` | Physical CPU cores allocated per pod |
| `storage.directIoPath` | `string` | `"/mnt/nvme"` | HostPath volume for Direct I/O targets |
| `storage.blockSizeBytes` | `int` | `1048576` | Block transfer size (1 MB default) |
| `workload.targetThroughputGbps` | `float` | `100.0` | Target aggregate cluster throughput |
| `workload.entropyRatio` | `float` | `0.8` | In-place payload randomness ratio |
| `telemetry.prometheus.enabled` | `bool` | `true` | Expose Prometheus metrics endpoint |
| `telemetry.prometheus.port` | `int` | `8000` | Telemetry metrics exposition port |

---

## Uninstalling

```bash
helm uninstall setve-cluster --namespace setve-system
```
