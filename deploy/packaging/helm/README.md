# SETVE Helm 3 Packaging (`deploy/packaging/helm/`)

Production Helm 3 chart for deploying distributed SETVE load generator worker pools onto dedicated bare-metal Kubernetes nodes.

---

## Structure
- **`setve-cluster/`**: Standard Helm 3 package.
  - `Chart.yaml`: Helm chart metadata.
  - `values.yaml`: Default configuration values.
  - `templates/`: Manifests for master deployment, worker daemonset, and gRPC/Prometheus services.

---

## Installation
```bash
helm install setve-cluster deploy/packaging/helm/setve-cluster \
  --namespace setve-system \
  --create-namespace \
  --values deploy/environments/staging/values.staging.yaml
```
