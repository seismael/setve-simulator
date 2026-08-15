# SETVE Production Use Cases & Engineering Recipes

This directory contains standalone, production-ready scenario scripts showcasing the full architectural capability spectrum of the **Universal Simulation & Telemetry Validation Engine (SETVE)**.

---

## Use Case Matrix & Subsystem Mapping

| # | Scenario Script | Domain | Target Subsystems | Primary Engineering Metric |
| :- | :--- | :--- | :--- | :--- |
| **01** | [`usecase_01_storage_stress.py`](file:///c:/dev/projects/setve-simulator/usecases/usecase_01_storage_stress.py) | Data Plane | `PosixDirectIOAdapter`, `MultiCoreOrchestrator` | Aggregate Gbps, IOPS, Core Pinning |
| **02** | [`usecase_02_dedup_compression.py`](file:///c:/dev/projects/setve-simulator/usecases/usecase_02_dedup_compression.py) | Payload Engine | `PySIMDPayloadMutator`, AVX-512 SIMD | Shannon Entropy, LZ4/Zstandard Savings % |
| **03** | [`usecase_03_prometheus_monitoring.py`](file:///c:/dev/projects/setve-simulator/usecases/usecase_03_prometheus_monitoring.py) | Observability | `MetricCollector`, Prometheus `/metrics`, JSON | Sub-ms Latency Percentiles ($p_{50}, p_{90}, p_{99}$) |
| **04** | [`usecase_04_ebpf_triangulation.py`](file:///c:/dev/projects/setve-simulator/usecases/usecase_04_ebpf_triangulation.py) | Validation | `EBPFProbe`, `TelemetryEvaluator` | Wire vs Client Skew ($\le 0.1\%$ SLA) |
| **05** | [`usecase_05_ai_vector_s3.py`](file:///c:/dev/projects/setve-simulator/usecases/usecase_05_ai_vector_s3.py) | Target Drivers | `VectorTargetAdapter`, `S3TargetAdapter` | Upsert IOPS, Nearest-Neighbor QPS |
| **06** | [`usecase_06_ai_kv_cache_checkpointing.py`](file:///c:/dev/projects/setve-simulator/usecases/usecase_06_ai_kv_cache_checkpointing.py) | AI Data Plane | Prefill Burst, KV-Cache Decode, Checkpoints | Time-To-First-Token (TTFT), ITL ($p_{99}$) |
| **07** | [`usecase_07_multitenant_qos_noisy_neighbor.py`](file:///c:/dev/projects/setve-simulator/usecases/usecase_07_multitenant_qos_noisy_neighbor.py) | Control Plane | Multi-Tenant QoS, Contention Auditing | Tail Inflation Ratio ($p_{99}$ Jitter Multiplier) |
| **08** | [`usecase_08_chaos_node_failure.py`](file:///c:/dev/projects/setve-simulator/usecases/usecase_08_chaos_node_failure.py) | Distributed | `DeterministicShardGenerator`, Node Eviction | Dynamic Shard Rebalance Latency ($\mu\text{s}$) |
| **09** | [`usecase_09_storage_tiering_lifecycle.py`](file:///c:/dev/projects/setve-simulator/usecases/usecase_09_storage_tiering_lifecycle.py) | Target Flow | Hot NVMe $\rightarrow$ Warm Block $\rightarrow$ Cold S3 | Lifecycle Storage Cost Reduction (% ROI) |
| **10** | [`usecase_10_tail_latency_microburst.py`](file:///c:/dev/projects/setve-simulator/usecases/usecase_10_tail_latency_microburst.py) | Observability | 64-Bucket HDR Histogram, Micro-Burst Spikes | $p_{99.9} / p_{99.99}$ Tail Latency Degradation |

---

## 1. Storage Saturation Stress Testing (`usecase_01_storage_stress.py`)

### Problem Statement
Standard file I/O tests often hit OS page-cache buffering, producing artificial gigabytes-per-second benchmarks that mask physical NVMe/storage bus bottlenecks.

### Solution
Executes zero-copy Direct I/O (`O_DIRECT`), enforcing strict $4096\text{-byte}$ memory alignment and dedicated process-per-core CPU affinity via `os.sched_setaffinity`.

```bash
# Basic run with temporary storage
python usecases/usecase_01_storage_stress.py

# High-performance multi-core saturation targeting a specific mount
python usecases/usecase_01_storage_stress.py \
  --target /mnt/nvme0/stress_target.dat \
  --block-size 1048576 \
  --throughput 50.0 \
  --duration 5.0 \
  --cores 8 \
  --queue-depth 32
```

---

## 2. Deduplication & Compression Validation (`usecase_02_dedup_compression.py`)

### Problem Statement
Storage systems using inline deduplication or hardware compression (e.g. ZFS, Pure Storage, Ceph) yield deceptive performance if benchmarks use zeroes or simple repetitive patterns.

### Solution
Uses the AVX-512 `PySIMDPayloadMutator` to generate in-place dynamic entropy across the full compression spectrum ($\alpha \in [0.0, 1.0]$), calculating empirical Shannon entropy $H(X) = -\sum P(x) \log_2 P(x)$ and estimating theoretical LZ4/Zstandard savings.

```bash
python usecases/usecase_02_dedup_compression.py --buffer-size-mb 2 --iterations 1000
```

---

## 3. Prometheus & Telemetry Ingestion (`usecase_03_prometheus_monitoring.py`)

### Problem Statement
Monitoring systems require structured, standard metrics exposition format with sub-millisecond percentile precision for telemetry ingestion pipelines.

### Solution
Emits real-time Prometheus text exposition format (`/metrics`), logarithmic HDR latency percentiles ($p_{50}, p_{90}, p_{99}$), and structured JSON telemetry for ClickHouse and Elasticsearch.

```bash
python usecases/usecase_03_prometheus_monitoring.py \
  --duration 3.0 \
  --throughput 20.0 \
  --output-prom /tmp/metrics.prom \
  --output-json /tmp/telemetry.json
```

---

## 4. Out-of-Band eBPF Telemetry Triangulation (`usecase_04_ebpf_triangulation.py`)

### Problem Statement
Software-reported client throughput metrics can deviate from physical hardware reality due to socket buffering, TCP retransmissions, or unmonitored background tenant activity.

### Solution
Triangulates client-reported transfer counters against out-of-band kernel/NIC hardware probes (`EBPFProbe`) using `TelemetryEvaluator`, auditing metric skew against a strict $\le 0.1\%$ SLA with automated diagnostic root-cause classification.

```bash
# Valid telemetry audit
python usecases/usecase_04_ebpf_triangulation.py --transfer-mb 2048 --tolerance 0.1

# Injected skew simulation (5 MB drift)
python usecases/usecase_04_ebpf_triangulation.py --transfer-mb 2048 --drift-bytes 5000000
```

---

## 5. AI Vector Database & S3 Ingestion (`usecase_05_ai_vector_s3.py`)

### Problem Statement
Modern AI infrastructure pipelines require concurrent handling of high-frequency vector embedding upserts/queries alongside large multipart model weight transfers.

### Solution
Simulates dual-target workloads: high-frequency 1536-dimensional vector upserts and nearest-neighbor top-K queries against vector engines (Milvus, Pinecone, Qdrant) alongside $5\text{ MB}$ multipart S3 object stream ingestion.

```bash
python usecases/usecase_05_ai_vector_s3.py --vector-ops 5000 --vector-queries 500 --s3-chunks 50
```

---

## 6. AI LLM KV-Cache & Model Checkpointing (`usecase_06_ai_kv_cache_checkpointing.py`)

### Problem Statement
Large Language Model (LLM) inference and training present conflicting I/O patterns: huge sequential prefill ingestion, random fine-grained $4\text{ KB}$ KV-cache token updates, and massive periodic checkpoint weight flushes.

### Solution
Executes a realistic 3-phase AI simulation measuring Time-To-First-Token (TTFT), Inter-Token Latency (ITL) percentiles, and checkpoint flush throughput.

```bash
python usecases/usecase_06_ai_kv_cache_checkpointing.py \
  --prefill-mb 256 \
  --tokens 5000 \
  --checkpoint-mb 512
```

---

## 7. Multi-Tenant QoS & Resource Contention (`usecase_07_multitenant_qos_noisy_neighbor.py`)

### Problem Statement
Multi-tenant storage clouds suffer from "noisy neighbor" interference, where unthrottled batch analytics jobs degrade mission-critical OLTP tail latency.

### Solution
Models latency-critical Tenant A ($4\text{ KB}$ OLTP with $p_{99} \le 2.0\text{ ms}$ SLA) running in isolation vs running concurrently with unthrottled Tenant B ($1\text{ MB}$ bulk writes), reporting jitter amplification factors.

```bash
python usecases/usecase_07_multitenant_qos_noisy_neighbor.py \
  --tenant-a-ops 2500 \
  --tenant-b-mb 128 \
  --sla-ms 2.5
```

---

## 8. Distributed Chaos Engineering & Shard Rebalancing (`usecase_08_chaos_node_failure.py`)

### Problem Statement
Distributed load generator clusters must dynamically handle hardware crashes and node evictions mid-test without producing unassigned target address gaps or overlapping collisions.

### Solution
Simulates a multi-node cluster (e.g. 16 nodes, 128 cores) undergoing sudden node failure and recovery, validating deterministic SplitMix64 shard rebalancing and $100\%$ contiguous address space preservation in microsecond time bounds.

```bash
python usecases/usecase_08_chaos_node_failure.py --nodes 16 --cores-per-node 8 --failed-nodes 4 --target-gb 1024
```

---

## 9. Multi-Tier Storage Lifecycle & Economics (`usecase_09_storage_tiering_lifecycle.py`)

### Problem Statement
Enterprise storage tiers need automated data demotion from expensive ultra-fast NVMe to cost-effective object storage without losing data pipeline throughput.

### Solution
Simulates data demotion through Hot Tier (NVMe / $4\text{ KB}$ random) $\rightarrow$ Warm Tier (Block / $1\text{ MB}$ sequential staging) $\rightarrow$ Cold Tier (S3 / $5\text{ MB}$ compressed multipart), calculating storage economics and ROI savings percentages.

```bash
python usecases/usecase_09_storage_tiering_lifecycle.py --hot-ops 3000 --warm-mb 128 --cold-chunks 20
```

---

## 10. Tail-Latency Micro-Burst & Jitter Analysis (`usecase_10_tail_latency_microburst.py`)

### Problem Statement
Traditional 15-second metric scrapers (like default Prometheus setups) average out periodic $50\text{ ms}$ traffic surges, concealing catastrophic $p_{99.9} / p_{99.99}$ tail-latency spikes and bufferbloat.

### Solution
Injects unpaced micro-burst surges against steady-state traffic and uses a 64-bucket logarithmic HDR histogram to render visual ASCII distribution density profiles and calculate exact tail degradation multipliers.

```bash
python usecases/usecase_10_tail_latency_microburst.py --steady-ops 3000 --burst-cycles 5 --burst-intensity 500
```
