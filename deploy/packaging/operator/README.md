# STEVE Kubernetes Operator Packaging (`deploy/packaging/operator/`)

Declarative, event-driven Kubernetes Operator built with [Kopf](https://kopf.readthedocs.io/) for managing `STEVECluster` Custom Resources.

---

## Custom Resource Definition (`STEVECluster`)
Located at `crds/stevecluster-crd.yaml`.

```yaml
apiVersion: steve.io/v1alpha1
kind: STEVECluster
metadata:
  name: nvme-storage-stress
  namespace: steve-system
spec:
  nodeCount: 16
  coresPerNode: 16
  targetThroughputGbps: 200
  targetEndpoint: "posix:///mnt/nvme/data.dat"
  blockSizeBytes: 1048576
  entropyRatio: 0.85
  workloadDurationSeconds: 60
```

---

## Running the Controller
```bash
python deploy/packaging/operator/controller.py
```
