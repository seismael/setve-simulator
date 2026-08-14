"""SETVE Use Case 07: Multi-Tenant Quality of Service (QoS) & Noisy Neighbor Contention.

Simulates multi-tenant storage resource competition:
1. Tenant A (Latency-Sensitive OLTP): High-priority 4 KB I/O with tail-latency SLA (p99 <= 2.0ms).
2. Tenant B (Batch Analytics / Noisy Neighbor): High-throughput unthrottled 1 MB bulk write stream.
Evaluates QoS throttling, tail-latency inflation, and bandwidth fair-sharing.
"""

import argparse
import asyncio
import sys
import time
from pathlib import Path

# Ensure setve package is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from setve.adapters.base import TargetDescriptor  # noqa: E402
from setve.adapters.factory import AdapterFactory  # noqa: E402
from setve.payload.buffer_pool import BufferPool  # noqa: E402
from setve.payload.mutator import PySIMDPayloadMutator  # noqa: E402
from setve.validation.metric_collector import MetricCollector  # noqa: E402


async def run_tenant_a_oltp(
    adapter: object,
    target: TargetDescriptor,
    ops: int,
    collector: MetricCollector,
) -> None:
    """Execute Tenant A (Latency-Critical OLTP) workload."""
    pool = BufferPool(buffer_count=4, buffer_size=4096)
    try:
        for i in range(ops):
            buf = pool.acquire(i)
            t0 = time.perf_counter_ns()
            w = await adapter.write(target, offset=(i * 4096) % 10485760, payload=buf)
            collector.record_latency(time.perf_counter_ns() - t0)
            collector.record_bytes(w)
            await asyncio.sleep(0.0001)  # Simulated token-bucket rate pacing
    finally:
        pool.close()


async def run_tenant_b_noisy_neighbor(
    adapter: object,
    target: TargetDescriptor,
    chunks: int,
    collector: MetricCollector,
) -> None:
    """Execute Tenant B (Noisy Neighbor Batch Saturation) workload."""
    mutator = PySIMDPayloadMutator(1048576)  # 1 MB blocks
    for i in range(chunks):
        buf = mutator.apply_entropy(0, 1048576, seed=i)
        t0 = time.perf_counter_ns()
        w = await adapter.write(target, offset=i * 1048576, payload=buf)
        collector.record_latency(time.perf_counter_ns() - t0)
        collector.record_bytes(w)



async def run_multitenant_qos_simulation(
    tenant_a_ops: int = 1500,
    tenant_b_mb: int = 64,
    target_uri: str = "posix:///tmp/qos_sim_target.dat",
) -> int:
    """Execute multi-tenant QoS contention benchmark."""
    print("=" * 80)
    print("  SETVE USE CASE 07: Multi-Tenant QoS & Noisy Neighbor Contention")
    print("=" * 80)

    adapter = AdapterFactory.create(target_uri)
    await adapter.initialize({"direct_io": False})

    target_a = TargetDescriptor(endpoint_uri=target_uri, resource_path="tenant_a_oltp.dat")
    target_b = TargetDescriptor(endpoint_uri=target_uri, resource_path="tenant_b_batch.dat")

    collector_a_baseline = MetricCollector()
    collector_a_contended = MetricCollector()
    collector_b = MetricCollector()

    # Step 1: Baseline Tenant A execution (Isolated)
    print(f"\n[*] Running Tenant A in isolation ({tenant_a_ops:,} ops)...")
    await run_tenant_a_oltp(adapter, target_a, tenant_a_ops, collector_a_baseline)
    baseline_p99 = collector_a_baseline.percentile_ms(0.99)

    # Step 2: Contended Execution (Tenant A + Tenant B Concurrent)
    print(
        f"[*] Running Tenant A + Noisy Neighbor Tenant B concurrently "
        f"({tenant_b_mb} MB batch)..."
    )
    t0_concurrent = time.perf_counter_ns()
    await asyncio.gather(
        run_tenant_a_oltp(adapter, target_a, tenant_a_ops, collector_a_contended),
        run_tenant_b_noisy_neighbor(adapter, target_b, tenant_b_mb, collector_b),
    )
    concurrent_duration = max((time.perf_counter_ns() - t0_concurrent) / 1e9, 1e-9)

    contended_p50 = collector_a_contended.percentile_ms(0.50)
    contended_p99 = collector_a_contended.percentile_ms(0.99)
    tenant_b_gbps = (collector_b.total_bytes * 8) / concurrent_duration / 1e9

    jitter_ratio = contended_p99 / max(baseline_p99, 0.001)
    qos_status = "PASS (SLA MET)" if contended_p99 <= 2.0 else "FAIL (QoS VIOLATION)"

    print("\n+--------------------------------------------------------------------------------+")
    print("| MULTI-TENANT QUALITY OF SERVICE (QoS) AUDIT                                    |")
    print("+--------------------------------------------------------------------------------+")
    print(f"| Tenant A Baseline (p99):       {baseline_p99:>16.3f} ms                           |")
    print(f"| Tenant A Contended (p50):      {contended_p50:>16.3f} ms                           |")
    print(f"| Tenant A Contended (p99):      {contended_p99:>16.3f} ms                           |")
    print(f"| Contention Jitter Inflation:   {jitter_ratio:>16.2f}x                            |")
    print(f"| Tenant B Consumed Bandwidth:   {tenant_b_gbps:>16.2f} Gbps                         |")
    print(f"| Tenant A QoS SLA Verification: {qos_status:>24}        |")
    print("+--------------------------------------------------------------------------------+\n")

    return 0


def main() -> int:
    """Parse CLI options and run multi-tenant QoS simulation."""
    parser = argparse.ArgumentParser(
        description="SETVE Use Case 07: Multi-Tenant QoS & Resource Contention Simulation"
    )
    parser.add_argument(
        "--tenant-a-ops",
        type=int,
        default=1000,
        help="Number of latency-sensitive OLTP operations",
    )
    parser.add_argument(
        "--tenant-b-mb",
        type=int,
        default=32,
        help="Volume of noisy-neighbor batch payload in MB",
    )
    parser.add_argument(
        "--target-uri",
        type=str,
        default="posix:///tmp/qos_sim_target.dat",
        help="Target storage URI",
    )
    args = parser.parse_args()

    return asyncio.run(
        run_multitenant_qos_simulation(
            tenant_a_ops=args.tenant_a_ops,
            tenant_b_mb=args.tenant_b_mb,
            target_uri=args.target_uri,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
