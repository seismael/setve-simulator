# SETVE Local Developer Environment (`deploy/environments/local/`)

Self-contained local developer runtime powered by Docker Compose.

---

## Included Services
1. **`setve-orchestrator`**: SETVE execution master and worker runtime (`:9100`, `:50051`).
2. **`minio`**: Mock high-performance S3 object storage server (`:9000`, `:9001`).
3. **`prometheus`**: Scrapes telemetry metrics at 1-second intervals (`:9090`).
4. **`grafana`**: Real-time visualization dashboard (`:3000`).

---

## Launching Local Environment
```bash
docker compose -f deploy/environments/local/docker-compose.yml up --build -d
```

## Access Points
- **Grafana Live Dashboard**: `http://localhost:3000` (Login: `admin` / `admin`)
- **Prometheus Metrics**: `http://localhost:9090`
- **MinIO Storage Console**: `http://localhost:9001` (Login: `minioadmin` / `minioadmin`)
