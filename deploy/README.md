# STEVE Enterprise Deployment & Infrastructure Architecture

This directory houses the unified deployment and infrastructure ecosystem for the **Storage, Telemetry, Engine, Verification, and Evaluation (STEVE)**.

---

## 3-Tier Enterprise Structure Overview

```text
deploy/
├── README.md                      # Master Deployment & Infrastructure Architecture Guide
│
├── packaging/                     # 1. BUILD & PACKAGING SPECS (The "How to Build")
│   ├── docker/                    # Multi-stage Dockerfile & container entrypoint
│   │   ├── Dockerfile
│   │   ├── entrypoint.sh
│   │   └── README.md
│   ├── helm/                      # Production Kubernetes Helm 3 Chart
│   │   ├── README.md
│   │   └── steve-cluster/
│   │       ├── Chart.yaml
│   │       ├── values.yaml
│   │       └── templates/
│   └── operator/                  # Cloud-Native Kopf Kubernetes Operator & CRDs
│       ├── README.md
│       ├── controller.py
│       └── crds/
│           └── stevecluster-crd.yaml
│
├── environments/                  # 2. TARGET ENVIRONMENTS & OVERLAYS (The "Where to Run")
│   ├── README.md                  # Environment tier progression guide
│   ├── local/                     # Local Developer Stack (Docker Compose + MinIO + Prom + Grafana)
│   │   ├── docker-compose.yml
│   │   ├── prometheus.yml
│   │   ├── README.md
│   │   └── grafana/
│   ├── dev/                       # CI/CD Ephemeral Infrastructure (Terraform + Cloud-Init)
│   │   └── terraform/main.tf
│   ├── staging/                   # Pre-Production 8-Node Bare-Metal (Values Overlay)
│   │   └── values.staging.yaml
│   └── prod/                      # Hyperscale Multi-Terabyte Saturation (Values Overlay)
│       └── values.prod.yaml
│
└── emulator/                      # 3. LOCAL MULTI-NODE TESTING HARNESS (The "Cluster Simulator")
    ├── __init__.py                # Exports LocalClusterEmulator
    ├── cluster_runner.py          # Multi-process node fleet with live gRPC barrier sync
    └── README.md                  # Multi-node local testing guide
```

---

## 1. Packaging Specs (`deploy/packaging/`)

Contains immutable build definitions and distribution artifacts:
- **`packaging/docker/`**: Multi-stage Linux Docker build with `uv`, `libnuma-dev`, and core affinity capabilities (`CAP_SYS_NICE`, `CAP_SYS_ADMIN`).
- **`packaging/helm/steve-cluster/`**: Enterprise Helm 3 package for dedicated bare-metal Kubernetes nodes.
- **`packaging/operator/`**: Event-driven Kopf Kubernetes Operator managing declarative `STEVECluster` Custom Resources (`steve.io/v1alpha1`).

---

## 2. Environment Overlays (`deploy/environments/`)

Target-specific configurations and scaling policies:

| Environment | Purpose | Target Rate | Topology & Manifests |
| :--- | :--- | :--- | :--- |
| **`local`** | Local developer testing | $\le 10\text{ Gbps}$ | `deploy/environments/local/docker-compose.yml` |
| **`dev`** | CI/CD ephemeral clusters | $25\text{ Gbps}$ | `deploy/environments/dev/terraform/main.tf` |
| **`staging`** | Pre-production validation | $100\text{ Gbps}$ | `deploy/environments/staging/values.staging.yaml` |
| **`prod`** | Hyperscale stress testing | $\ge 1\text{ TB/s}$ | `deploy/environments/prod/values.prod.yaml` |

---

## 3. Local Cluster Emulator (`deploy/emulator/`)

Emulates a distributed multi-node storage load generation cluster entirely on local host infrastructure:
- **`cluster_runner.py`**: Spawns multiple simulated cluster nodes with dedicated worker process pools, executes live gRPC barrier synchronization handshakes, and aggregates cluster-wide HDR telemetry.
- **Run command**:
  ```bash
  python deploy/emulator/cluster_runner.py --nodes 4 --cores-per-node 2 --duration 3.0 --rate 10.0
  ```
