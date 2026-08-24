# STEVE Helm 3 Packaging (`deploy/packaging/helm/`)

Production Helm 3 chart for deploying distributed STEVE load generator worker pools onto dedicated bare-metal Kubernetes nodes.

---

## Structure
- **`steve-cluster/`**: Standard Helm 3 package.
  - `Chart.yaml`: Helm chart metadata.
  - `values.yaml`: Default configuration values.
  - `templates/`: Manifests for master deployment, worker daemonset, and gRPC/Prometheus services.

---

## Installation
```bash
helm install steve-cluster deploy/packaging/helm/steve-cluster \
  --namespace steve-system \
  --create-namespace \
  --values deploy/environments/staging/values.staging.yaml
```
