# SETVE Production Use Cases & Execution Guide

This directory contains standalone, production-ready scenario scripts showcasing the full capability spectrum of the **Universal Simulation & Telemetry Validation Engine (SETVE)**.

---

## Complete Use Case Catalog

| Scenario Script | Domain | Target Subsystems | CLI Execution |
| :--- | :--- | :--- | :--- |
| **`usecase_01_storage_stress.py`** | Data Plane | `PosixDirectIOAdapter`, `MultiCoreOrchestrator` | `python usecases/usecase_01_storage_stress.py` |
| **`usecase_02_dedup_compression.py`**| Payload | `PySIMDPayloadMutator`, AVX-512 Entropy | `python usecases/usecase_02_dedup_compression.py` |
| **`usecase_03_prometheus_monitoring.py`**| Observability | `MetricCollector`, Prometheus Text, JSON | `python usecases/usecase_03_prometheus_monitoring.py` |
| **`usecase_04_ebpf_triangulation.py`**| Validation | `EBPFProbe`, `TelemetryEvaluator` (<=0.1% SLA) | `python usecases/usecase_04_ebpf_triangulation.py` |
| **`usecase_05_ai_vector_s3.py`** | Target Drivers | `VectorTargetAdapter`, `S3TargetAdapter` | `python usecases/usecase_05_ai_vector_s3.py` |
| **`usecase_06_ai_kv_cache_checkpointing.py`**| AI Data Plane | Prefill Phase, Decode KV-Cache, Checkpoints | `python usecases/usecase_06_ai_kv_cache_checkpointing.py` |
| **`usecase_07_multitenant_qos_noisy_neighbor.py`**| Control Plane | Multi-Tenant QoS, Token-Bucket Throttling | `python usecases/usecase_07_multitenant_qos_noisy_neighbor.py` |
| **`usecase_08_chaos_node_failure.py`**| Distributed | `DeterministicShardGenerator`, Node Eviction | `python usecases/usecase_08_chaos_node_failure.py` |
| **`usecase_09_storage_tiering_lifecycle.py`**| Target Flow | Hot NVMe $\rightarrow$ Warm Block $\rightarrow$ Cold S3 | `python usecases/usecase_09_storage_tiering_lifecycle.py` |
| **`usecase_10_tail_latency_microburst.py`**| Observability | 64-Bucket HDR Histogram, $p_{99.99}$ Tail Spikes | `python usecases/usecase_10_tail_latency_microburst.py` |

---

## 1. Storage Saturation Stress Testing (`usecase_01_storage_stress.py`)
Stress-tests high-throughput NVMe block devices using zero-copy Direct I/O (`O_DIRECT`), bypassing the OS page cache with multi-process core pinning.

```bash
python usecases/usecase_01_storage_stress.py --target /mnt/nvme0/stress_target.dat --throughput 50.0 --cores 4
```

---

## 2. Deduplication & Compression Validation (`usecase_02_dedup_compression.py`)
Evaluates inline storage compression and deduplication algorithms across runtime entropy ratio sweeps ($\alpha \in [0.0, 1.0]$) at up to $15.5\text{ GB/s}$.

```bash
python usecases/usecase_02_dedup_compression.py --buffer-size-mb 1 --iterations 500
```

---

## 3. Prometheus & Telemetry Ingestion (`usecase_03_prometheus_monitoring.py`)
Emits live Prometheus exposition format (`/metrics`), sub-millisecond HDR latency percentiles ($p_{50}, p_{90}, p_{99}$), and structured JSON telemetry.

```bash
python usecases/usecase_03_prometheus_monitoring.py --duration 2.0 --throughput 10.0
```

---

## 4. Out-of-Band eBPF Telemetry Triangulation (`usecase_04_ebpf_triangulation.py`)
Mathematically audits client-reported throughput against kernel/hardware trace probes to verify telemetry accuracy ($\le 0.1\%$ SLA).

```bash
python usecases/usecase_04_ebpf_triangulation.py --transfer-mb 1024 --tolerance 0.1
```

---

## 5. AI Vector Database & S3 Ingestion (`usecase_05_ai_vector_s3.py`)
Simulates parallel ingestion for high-density vector embeddings (Milvus, Pinecone, Qdrant) and multipart S3 object streams (AWS S3, MinIO, Ceph).

```bash
python usecases/usecase_05_ai_vector_s3.py --vector-ops 2000 --s3-chunks 30
```

---

## 6. AI LLM KV-Cache & Model Checkpointing (`usecase_06_ai_kv_cache_checkpointing.py`)
Simulates heterogeneous LLM inference and training traffic: bursty sequential prefill passes, high-concurrency $4\text{ KB}$ KV-cache decode updates, and multi-gigabyte background weight flushes.

```bash
python usecases/usecase_06_ai_kv_cache_checkpointing.py --prefill-mb 128 --tokens 2000 --checkpoint-mb 256
```

---

## 7. Multi-Tenant QoS & Resource Contention (`usecase_07_multitenant_qos_noisy_neighbor.py`)
Models mission-critical Tier-1 OLTP workloads ($p_{99} \le 2.0\text{ ms}$) contending against unthrottled batch analytics noisy neighbors on shared NVMe channels.

```bash
python usecases/usecase_07_multitenant_qos_noisy_neighbor.py --tenant-a-ops 2000 --tenant-b-mb 64
```

---

## 8. Distributed Chaos Engineering & Shard Rebalancing (`usecase_08_chaos_node_failure.py`)
Simulates a 16-node / 128-core distributed generator cluster undergoing sudden $25\%$ node crash/eviction, validating deterministic dynamic shard rebalancing and zero address gap coverage.

```bash
python usecases/usecase_08_chaos_node_failure.py --nodes 16 --cores-per-node 8 --failed-nodes 4
```

---

## 9. Multi-Tier Storage Lifecycle (`usecase_09_storage_tiering_lifecycle.py`)
Models automated data aging and demotion pipelines across Hot NVMe ($4\text{ KB}$ random) $\rightarrow$ Warm Block ($1\text{ MB}$ staging) $\rightarrow$ Cold S3 Object Store ($5\text{ MB}$ multipart archive).

```bash
python usecases/usecase_09_storage_tiering_lifecycle.py --hot-ops 2000 --warm-mb 64 --cold-chunks 10
```

---

## 10. Tail-Latency Micro-Burst & Jitter Analysis (`usecase_10_tail_latency_microburst.py`)
Generates periodic $50\text{ ms}$ $100\times$ traffic surges to stress queue depth and capture sub-millisecond $p_{99.9} / p_{99.99}$ tail-latency spikes missed by standard 15-second metric scrapers.

```bash
python usecases/usecase_10_tail_latency_microburst.py --steady-ops 2000 --burst-cycles 5 --burst-intensity 500
```
