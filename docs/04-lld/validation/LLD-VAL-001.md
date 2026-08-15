---
id: "LLD-VAL-001"
title: "Telemetry Metric Collection, HDR Histogram, eBPF Probe & Divergence Evaluator"
type: "LLD"
status: "APPROVED"
domain: "data-plane"
layer: "compute-engine"
c4_level: "code"
diataxis_type: "reference"
traceability:
  implements_brd: ["BRD-SETVE-001"]
  governed_by_adr: ["ADR-0001"]
  parent_hld: "HLD-SETVE-001"
  child_llds: []
code_references:
  - "setve/validation/metric_collector.py"
  - "setve/validation/reporter.py"
  - "setve/validation/ebpf_probe.py"
  - "setve/validation/evaluator.py"
test_references:
  - "tests/test_metric_collector.py"
  - "tests/test_reporter.py"
  - "tests/test_telemetry_evaluator.py"
  - "tests/test_master_telemetry.py"
owner: "@architecture-team"
last_validated_date: "2026-08-05"
---

# LLD-VAL-001: Telemetry Metric Collection, HDR Histogram, eBPF Probe & Divergence Evaluator

## 1. Module Overview & Subsystem Architecture

`LLD-VAL-001` specifies the concrete design and memory layout of the SETVE observability, metric collection, and validation plane. The subsystem ensures zero heap allocations on hot data-plane loops while providing sub-microsecond latency profiling ($p_{50}, p_{90}, p_{99}, p_{99.9}$) and out-of-band ground-truth hardware counter triangulation ($\le 0.1\%$ skew SLA).

```text
┌─────────────────────────────────────────────────────────────────────────────────┐
│                   METRIC TRIANGULATION & ARBITRATION CONTEXT                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   ┌───────────────────────────┐                ┌────────────────────────────┐   │
│   │ SETVE Distributed Cluster │  Stress Load   │ System Under Test (SUT)    │   │
│   │ (4-64 Core-Pinned Nodes)  │ ─────────────> │ (NVMe-oF / POSIX / S3 / DB)│   │
│   └─────────────┬─────────────┘                └─────────────┬──────────────┘   │
│                 │                                            │                  │
│                 │ In-Band Client Telemetry                   │ SUT Telemetry    │
│                 v                                            v                  │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │               TELEMETRY EVALUATOR (Divergence Arbitration)              │   │
│   │   (Validates if SUT matches physical Linux eBPF / XDP wire reality)     │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 1.1 Data Plane & Master Telemetry Pipeline

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        DATA PLANE WORKER LOOP                          │
│                                                                        │
│   t0 = perf_counter_ns()                                               │
│   bytes_written = adapter.write(...)                                   │
│   elapsed_ns = perf_counter_ns() - t0                                  │
│                                                                        │
│   ┌──────────────────────────────────────────────────────────────┐     │
│   │ MetricCollector.record_latency(elapsed_ns) [Zero-Alloc O(1)] │     │
│   │ MetricCollector.record_bytes(bytes_written)                  │     │
│   └──────────────────────────────────────────────────────────────┘     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Worker Completion
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│              WorkerTelemetryResult (Serialized to IPC Queue)           │
│   - Total Ops, Total Bytes, Duration                                   │
│   - p50, p90, p99, p99.9 Latency Percentiles (Calculated from HDR)     │
│   - Throughput (Gbps)                                                  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Aggregated by Master
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        MASTER TELEMETRY ENGINE                         │
│                                                                        │
│   ClusterTelemetrySummary ◄─── EBPFProbe (Hardware Interface Wire)     │
│             │                                                          │
│             ├──► TelemetryEvaluator (Computes Skew: Client vs Probe)   │
│             ├──► to_prometheus_metrics() (Prometheus /metrics Text)    │
│             ├──► to_json() (ClickHouse / Elasticsearch Sink)           │
│             └──► format_table() (ASCII Terminal Diagnostics)           │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 64-Bucket Logarithmic HDR Histogram (`MetricCollector`)

To guarantee zero allocations and prevent memory fragmentation inside high-frequency ($> 1\text{ M ops/s}$) worker loops, `MetricCollector` implements a 64-bucket logarithmic indexing model:

$$\text{Bucket Index}(t) = \min(63, \max(0, \lfloor \log_2(t_{\text{ns}}) \rfloor))$$

```text
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                               64-BUCKET LOGARITHMIC HDR HISTOGRAM                               │
├─────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                 │
│   Elapsed Latency (t_ns)                                                                        │
│   └─► Bucket Index = min(63, max(0, floor(log2(t_ns))))                                         │
│                                                                                                 │
│   ┌───────────────┬───────────────────────────────┬──────────────────────────────────────────┐  │
│   │ Bucket Index  │ Latency Range                 │ Scale Classification                     │  │
│   ├───────────────┼───────────────────────────────┼──────────────────────────────────────────┤  │
│   │ Bucket 0      │ < 1 ns                        │ Sub-Nanosecond                           │  │
│   │ Bucket 10     │ ~1.02 us (1,024 ns)           │ Microsecond Flash Line Rate              │  │
│   │ Bucket 20     │ ~1.05 ms (1,048,576 ns)       │ Millisecond Storage Spikes               │  │
│   │ Bucket 30     │ ~1.07 s                       │ High-Latency Timeout Threshold           │  │
│   │ Bucket 63     │ Up to 9.22 x 10^18 ns         │ Overflow Protection                      │  │
│   └───────────────┴───────────────────────────────┴──────────────────────────────────────────┘  │
│                                                                                                 │
│   Percentile Calculation (p50, p90, p99, p99.9) resolved via cumulative bucket distribution.   │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 2.1 Bucket Resolution & Latency Range
* **Bucket 0:** $< 1\text{ ns}$
* **Bucket 10:** $\sim 1\text{ }\mu\text{s}$ ($1,024\text{ ns}$)
* **Bucket 20:** $\sim 1\text{ ms}$ ($1,048,576\text{ ns}$)
* **Bucket 30:** $\sim 1.07\text{ s}$
* **Bucket 63:** Up to $9.22 \times 10^{18}\text{ ns}$ (Overflow protection)

---

## 3. Ground-Truth Hardware Triangulation (`TelemetryEvaluator`)

Out-of-band validation compares client-reported transferred bytes against kernel trace probes (`EBPFProbe`):

$$\text{Metric Skew (\%)} = \frac{|\text{Bytes}_{\text{Client}} - \text{Bytes}_{\text{Probe}}|}{\max(\text{Bytes}_{\text{Probe}}, 1)} \times 100$$

* **SLA Threshold:** $\text{Skew} \le 0.1\%$
* **Evaluation Status:** `DivergenceResult.is_valid = (divergence_percent <= skew_threshold_percent)`

---

## 4. Telemetry Exporters (`setve/validation/reporter.py`)

1. **Prometheus Text Format (`to_prometheus_metrics`)**:
   - `setve_cluster_ops_total{run_id="..."}`
   - `setve_cluster_bytes_total{run_id="..."}`
   - `setve_cluster_throughput_gbps{run_id="..."}`
   - `setve_cluster_latency_p99_ms{run_id="..."}`
   - `setve_telemetry_divergence_percent{run_id="..."}`
   - `setve_telemetry_is_valid{run_id="..."}`

2. **JSON Sink (`to_json`)**: Complete typed JSON serialization for ClickHouse or Elasticsearch telemetry ingest.
3. **ASCII Diagnostic Table (`format_table`)**: Formatted multi-column summary report safe for all terminal encodings (CP1252/UTF-8).
