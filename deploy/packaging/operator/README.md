# SETVE Kubernetes Operator Packaging (`deploy/packaging/operator/`)

Declarative, event-driven Kubernetes Operator built with [Kopf](https://kopf.readthedocs.io/) for managing `SETVECluster` Custom Resources.

---

## Custom Resource Definition (`SETVECluster`)
Located at `crds/setvecluster-crd.yaml`.

```yaml
apiVersion: setve.io/v1alpha1
kind: SETVECluster
metadata:
  name: nvme-storage-stress
  namespace: setve-system
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
