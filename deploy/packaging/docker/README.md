# SETVE Container Packaging (`deploy/packaging/docker/`)

Multi-stage, Linux-optimized Dockerfile recipe for the **Universal Simulation & Telemetry Validation Engine (SETVE)**.

---

## Features
- **Multi-Stage Build**: Utilizes `uv` in the builder stage to resolve and install Python packages in $< 1\text{ second}$.
- **Minimal Runtime**: Python 3.12-slim base image with `libnuma-dev` for hardware NUMA topology inspection.
- **Direct I/O & Affinity Capabilities**: Configured for `CAP_SYS_NICE` (CPU core pinning) and `CAP_SYS_ADMIN` (page-aligned Direct I/O).

---

## Building the Image Manually
```bash
docker build -t setve:latest -f deploy/packaging/docker/Dockerfile .
```
