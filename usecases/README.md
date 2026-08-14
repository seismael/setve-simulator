# SETVE Production Use Cases & Execution Guide

This directory contains standalone, production-ready scenario scripts showcasing key capabilities of the **Universal Simulation & Telemetry Validation Engine (SETVE)**.

---

## Use Case Catalog

| Script | Module Name | Domain | Key Subsystems Demonstrated |
| :--- | :--- | :--- | :--- |
| **`usecase_01_storage_stress.py`** | `usecases.usecase_01_storage_stress` | Data Plane | `PosixDirectIOAdapter`, `MultiCoreOrchestrator`, Core Pinning |
| **`usecase_02_dedup_compression.py`** | `usecases.usecase_02_dedup_compression` | Payload | `PySIMDPayloadMutator`, In-Place AVX-512 Entropy, Dedup Sweeps |
| **`usecase_03_prometheus_monitoring.py`** | `usecases.usecase_03_prometheus_monitoring` | Observability | `MetricCollector`, `ClusterTelemetrySummary`, Prometheus Text |
| **`usecase_04_ebpf_triangulation.py`** | `usecases.usecase_04_ebpf_triangulation` | Validation | `EBPFProbe`, `TelemetryEvaluator`, Skew SLA Verification |
| **`usecase_05_ai_vector_s3.py`** | `usecases.usecase_05_ai_vector_s3` | Target Drivers | `VectorTargetAdapter`, `S3TargetAdapter`, `AdapterFactory` |

---

## 1. Storage Saturation Stress Testing (`usecase_01_storage_stress.py`)

Stress-tests high-throughput storage devices using zero-copy Direct I/O (`O_DIRECT`), bypassing the OS page cache with multi-process core pinning.

```bash
# Basic run with temporary target (2 cores, 10 Gbps, 2 seconds)
python usecases/usecase_01_storage_stress.py

# Custom high-throughput run targeting specific mount
python usecases/usecase_01_storage_stress.py \
  --target /mnt/nvme0/stress_target.dat \
  --block-size 1048576 \
  --throughput 50.0 \
  --duration 5.0 \
  --cores 4 \
  --entropy 0.75
```

---

## 2. Deduplication & Compression Validation (`usecase_02_dedup_compression.py`)

Evaluates inline compression and deduplication resilience across variable entropy ratios ($0.0 = \text{100\% compressible}$ to $1.0 = \text{incompressible random data}$).

```bash
python usecases/usecase_02_dedup_compression.py --buffer-size-mb 1 --iterations 500
```

---

## 3. Prometheus & Telemetry Ingestion (`usecase_03_prometheus_monitoring.py`)

Executes a workload and generates Prometheus text exposition format, high-resolution HDR latency percentiles, and structured JSON telemetry.

```bash
python usecases/usecase_03_prometheus_monitoring.py --duration 2.0 --throughput 10.0
```

---

## 4. Out-of-Band eBPF Telemetry Triangulation (`usecase_04_ebpf_triangulation.py`)

Compares client-reported telemetry against out-of-band kernel/hardware trace probes to detect packet drops, timer drift, or metric inflation ($\le 0.1\%$ SLA).

```bash
# Valid telemetry pass
python usecases/usecase_04_ebpf_triangulation.py --transfer-mb 1024 --tolerance 0.1

# Injected skew test (e.g. 5 MB drift)
python usecases/usecase_04_ebpf_triangulation.py --transfer-mb 1024 --drift-bytes 5000000
```

---

## 5. AI Vector Database & S3 Ingestion (`usecase_05_ai_vector_s3.py`)

Simulates parallel ingestion for high-density vector embeddings (Milvus, Pinecone, Qdrant) and multipart S3 object streams (AWS S3, MinIO, Ceph).

```bash
python usecases/usecase_05_ai_vector_s3.py --vector-ops 2000 --s3-chunks 30
```
