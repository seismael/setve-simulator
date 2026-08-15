# Multi-Stage High-Performance Dockerfile for SETVE
# Stage 1: Build & Dependency Resolution
FROM python:3.12-slim AS builder

WORKDIR /build

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for ultra-fast dependency resolution
RUN pip install --no-cache-dir uv

COPY pyproject.toml /build/
COPY setve/ /build/setve/

RUN uv pip install --no-cache .

# Stage 2: Minimal Runtime
FROM python:3.12-slim AS runtime

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SETVE_ENV=container

RUN apt-get update && apt-get install -y --no-install-recommends \
    libnuma-dev \
    procps \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed site-packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY setve/ /app/setve/
COPY usecases/ /app/usecases/
COPY deploy/packaging/docker/entrypoint.sh /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh

# Expose Prometheus metric endpoint and gRPC sync port
EXPOSE 9100 50051

# Default volume mount points for high-performance direct I/O and SUT mounts
VOLUME ["/data", "/dev/shm"]

HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD curl -f http://localhost:9100/metrics || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "usecases/usecase_01_storage_stress.py"]
