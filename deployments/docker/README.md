# SETVE Local Containerized Deployment (Docker & Compose)

This deployment orchestrates the full **SETVE** simulation stack locally alongside mock storage targets (MinIO S3) and real-time observability telemetry (Prometheus & Grafana).

---

## Topology Architecture

```
                                  +-----------------------+
                                  |   Grafana (Port 3000) |
                                  +-----------+-----------+
                                              |
                                              v (Pulls metrics)
+-----------------------+         +-----------+-----------+
|   MinIO S3 (Port 9000)|         | Prometheus (Port 9090)|
+-----------+-----------+         +-----------+-----------+
            ^                                 ^
            | (S3 I/O Load)                   | (Scrapes /metrics)
+-----------+---------------------------------+-----------+
|               SETVE Orchestrator (Port 9100)            |
|   - Multi-Core Core-Pinned Worker Fleet                 |
|   - Zero-Allocation SIMD Payload Engine                 |
|   - Direct I/O / S3 Object Store Adapter                |
+---------------------------------------------------------+
```

---

## Quickstart

### 1. Build and Launch the Full Stack
```bash
cd deployments/docker
docker compose up --build -d
```

### 2. Service Endpoints
| Service | URL | Description |
| :--- | :--- | :--- |
| **SETVE Telemetry** | `http://localhost:9100/metrics` | Prometheus exposition endpoint |
| **Prometheus Web UI** | `http://localhost:9090` | Time-series query & graph UI |
| **Grafana Dashboard** | `http://localhost:3000` | Pre-provisioned real-time dashboard (`admin`/`admin`) |
| **MinIO Console** | `http://localhost:9001` | S3 Object store UI (`minioadmin`/`minioadmin`) |

### 3. Run Workload Use Cases Inside Container
```bash
# Execute NVMe Direct I/O Stress Run (Use Case 01)
docker compose exec setve-orchestrator python usecases/usecase_01_storage_stress.py

# Execute AI LLM KV-Cache Checkpointing (Use Case 06)
docker compose exec setve-orchestrator python usecases/usecase_06_ai_kv_cache_checkpointing.py

# Execute Tail-Latency Micro-Burst Benchmark (Use Case 10)
docker compose exec setve-orchestrator python usecases/usecase_10_tail_latency_microburst.py
```

### 4. Teardown
```bash
docker compose down -v
```
