# SETVE Deployment & Infrastructure Architecture

This directory houses the complete deployment ecosystem for the **Universal Simulation & Telemetry Validation Engine (SETVE)**, spanning local development environments to hyperscale, multi-node Kubernetes clusters.

---

## Deployment Options Overview

```text
┌───────────────────────────────────────────────────────────────────────────────────────┐
│                                SETVE DEPLOYMENT TOPOLOGIES                            │
├──────────────────────────┬──────────────────────────┬─────────────────────────────────┤
│ Tier / Topology          │ Target Runtime           │ Key Manifests & Controllers     │
├──────────────────────────┼──────────────────────────┼─────────────────────────────────┤
│ 1. Local Development     │ Docker Compose           │ deploy/environments/local/      │
│ 2. Production Kubernetes │ Helm 3 Chart             │ deploy/helm/setve-cluster/      │
│ 3. Cloud-Native Operator │ Kopf Operator + KEDA     │ deploy/k8s/operator/            │
│ 4. Multi-Cloud IaaS      │ Terraform + Cloud-Init   │ deploy/environments/dev/        │
└──────────────────────────┴──────────────────────────┴─────────────────────────────────┘
```

---

## 1. Local Development Topology (`deploy/environments/local/`)

Designed for single-node functional verification, telemetry debugging, and integration testing with an out-of-the-box Prometheus observability stack.

```bash
# Start local Prometheus telemetry stack
docker compose -f deploy/environments/local/docker-compose.local.yml up -d

# Scrape endpoint available at: http://localhost:9090
```

- **`docker-compose.local.yml`**: Spins up Prometheus, Grafana, and mock SUT targets.
- **`prometheus.yml`**: Configured to scrape SETVE metrics from `host.docker.internal:8000/metrics`.

---

## 2. Production Helm Chart (`deploy/helm/setve-cluster/`)

Package-managed deployment for dedicated bare-metal Kubernetes nodes with CPU pinning, host-path storage mounts, and SR-IOV network interfaces.

```bash
# Install SETVE Cluster chart
helm install setve-cluster deploy/helm/setve-cluster \
  --namespace setve-system \
  --create-namespace \
  --values deploy/helm/setve-cluster/values.yaml
```

### Key Values Configuration (`values.yaml`)
- `cluster.nodeCount`: Number of distributed load generator worker pods.
- `cluster.coresPerNode`: Physical cores dedicated per pod (pinned via `cpuset`).
- `storage.directIoPath`: Host block device or NVMe mount (`/dev/nvme0n1` or `/mnt/nvme`).
- `telemetry.prometheus.enabled`: Auto-generates Prometheus `ServiceMonitor` annotations.

---

## 3. Cloud-Native Kubernetes Operator (`deploy/k8s/operator/`)

A declarative, event-driven operator built with [Kopf](https://kopf.readthedocs.io/) that reconciles `SETVECluster` Custom Resources, dynamically calculating worker shard topologies and provisioning KEDA `ScaledObject` resources.

```bash
# Run operator controller in development mode
python deploy/k8s/operator/controller.py
```

### Declarative CRD Example (`SETVECluster`)
```yaml
apiVersion: setve.io/v1alpha1
kind: SETVECluster
metadata:
  name: nvme-saturation-cluster
  namespace: setve-system
spec:
  nodeCount: 16
  coresPerNode: 16
  targetThroughputGbps: 200
  targetUri: "posix:///mnt/nvme/target.dat"
  blockSizeBytes: 1048576
  entropyRatio: 0.85
  durationSeconds: 60
```

---

## 4. Multi-Tier Environments (`deploy/environments/`)

| Environment | Purpose | Target Throughput | Host Topology |
| :--- | :--- | :--- | :--- |
| **`local`** | Local developer testing | $\le 10\text{ Gbps}$ | Single process, loopback targets |
| **`dev`** | CI/CD ephemeral clusters | $25\text{ Gbps}$ | 2-4 virtualized nodes |
| **`staging`** | Pre-production validation | $100\text{ Gbps}$ | 8 bare-metal NVMe nodes |
| **`prod`** | Full-scale stress testing | $\ge 1\text{ TB/s}$ | 64+ core-pinned nodes, SR-IOV |
