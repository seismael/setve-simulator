# SETVE Environments Lifecycle & Infrastructure Guide

This guide details the multi-tier environment progression supporting SETVE from local testing to multi-terabyte production deployments.

---

## Environment Matrix

| Tier | Directory | Compute Topology | Storage Target | Observability Stack |
| :--- | :--- | :--- | :--- | :--- |
| **Local** | `deploy/environments/local/` | Single host (2-8 cores) | Temporary POSIX files / RAM disk | Docker Compose + Prometheus |
| **Dev** | `deploy/environments/dev/` | 2-4 virtual nodes | Emulated NVMe-oF / S3 MinIO | Ephemeral Prometheus |
| **Staging** | `deploy/environments/staging/`| 8 bare-metal nodes | Dual-port NVMe Direct I/O | Central Prometheus + ClickHouse |
| **Prod** | `deploy/environments/prod/` | 64+ core-pinned nodes | Multi-TB/s NVMe-oF fabric / SAN | Prometheus + eBPF Probes + Grafana |

---

## Local Environment Quickstart

```bash
# Start Prometheus container and local telemetry sink
docker compose -f deploy/environments/local/docker-compose.local.yml up -d

# Execute a simulation with telemetry output
python usecases/usecase_03_prometheus_monitoring.py
```
