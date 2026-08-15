"""SETVE Use Case 07: Multi-Tenant Quality of Service (QoS) & Noisy Neighbor Contention.

Simulates multi-tenant storage resource competition:
1. Tenant A (Latency-Sensitive OLTP): High-priority 4 KB I/O with tail-latency SLA (p99 <= 2.0ms).
2. Tenant B (Batch Analytics / Noisy Neighbor): High-throughput unthrottled 1 MB bulk write stream.
Evaluates QoS throttling, tail-latency inflation, and bandwidth fair-sharing.
"""

import argparse
import asyncio
import contextlib
import sys
import tempfile
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
            buf = pool.acquire(i % pool.buffer_count)
            t0 = time.perf_counter_ns()
            w = await adapter.write(target, offset=(i * 4096) % 10485760, payload=buf)
            collector.record_latency(time.perf_counter_ns() - t0)
            collector.record_bytes(w)
            await asyncio.sleep(0.0001)  # Simulated OLTP pacing
    finally:
        pool.close()


async def run_tenant_b_noisy_neighbor(
    adapter: object,
    target: TargetDescriptor,
    chunks: int,
    collector: MetricCollector,
    throttle_sleep_sec: float = 0.0,
) -> None:
    """Execute Tenant B (Noisy Neighbor Batch Saturation) workload."""
    mutator = PySIMDPayloadMutator(1048576)  # 1 MB blocks
    try:
        for i in range(chunks):
            buf = mutator.apply_entropy(0, 1048576, seed=i)
            t0 = time.perf_counter_ns()
            w = await adapter.write(target, offset=i * 1048576, payload=buf)
            collector.record_latency(time.perf_counter_ns() - t0)
            collector.record_bytes(w)
            if throttle_sleep_sec > 0:
                await asyncio.sleep(throttle_sleep_sec)
    finally:
        mutator.close()


async def run_multitenant_qos_simulation(
    tenant_a_ops: int = 1500,
    tenant_b_mb: int = 64,
    target_uri: str | None = None,
    sla_threshold_ms: float = 2.0,
    qos_throttle: bool = True,
) -> int:
    """Execute multi-tenant QoS contention benchmark."""
    print("=" * 80)
    print("  SETVE USE CASE 07: Multi-Tenant QoS & Noisy Neighbor Contention")
    print("=" * 80)

    cleanup_tmp = False
    tmp_dir = None
    if not target_uri:
        tmp_dir = tempfile.TemporaryDirectory()
        target_file = Path(tmp_dir.name) / "qos_sim_target.dat"
        target_uri = f"posix://{target_file}"
        cleanup_tmp = True
        print(f"[*] Target URI:                  {target_uri} (Temporary Storage)")
    else:
        print(f"[*] Target URI:                  {target_uri}")

    try:
        adapter = AdapterFactory.create(target_uri)
        await adapter.initialize({"direct_io": False})

        target_a = TargetDescriptor(endpoint_uri=target_uri, resource_path="tenant_a_oltp.dat")
        target_b = TargetDescriptor(endpoint_uri=target_uri, resource_path="tenant_b_batch.dat")

        collector_a_baseline = MetricCollector()
        collector_a_contended = MetricCollector()
        collector_b_unthrottled = MetricCollector()
        collector_a_qos = MetricCollector()
        collector_b_qos = MetricCollector()

        # Step 1: Baseline Tenant A execution (Isolated)
        print(f"\n[Phase 1: Baseline] Running Tenant A in isolation ({tenant_a_ops:,} ops)...")
        await run_tenant_a_oltp(adapter, target_a, tenant_a_ops, collector_a_baseline)
        baseline_p99 = collector_a_baseline.percentile_ms(0.99)
        print(f"[+] Tenant A Baseline p99: {baseline_p99:.3f} ms")

        # Step 2: Contended Execution (Tenant A + Unthrottled Tenant B)
        print(
            f"\n[Phase 2: Contention] Running Tenant A + Noisy Neighbor ({tenant_b_mb} MB batch)..."
        )
        t0_concurrent = time.perf_counter_ns()
        await asyncio.gather(
            run_tenant_a_oltp(adapter, target_a, tenant_a_ops, collector_a_contended),
            run_tenant_b_noisy_neighbor(
                adapter, target_b, tenant_b_mb, collector_b_unthrottled, throttle_sleep_sec=0.0
            ),
        )
        concurrent_duration = max((time.perf_counter_ns() - t0_concurrent) / 1e9, 1e-9)

        contended_p50 = collector_a_contended.percentile_ms(0.50)
        contended_p99 = collector_a_contended.percentile_ms(0.99)
        unthrottled_b_gbps = (collector_b_unthrottled.total_bytes * 8) / concurrent_duration / 1e9
        jitter_ratio = contended_p99 / max(baseline_p99, 0.001)

        # Step 3: QoS Enforced Execution (Token-bucket rate-limiting on Tenant B)
        qos_p99 = contended_p99
        qos_b_gbps = unthrottled_b_gbps
        if qos_throttle:
            print(
                "\n[Phase 3: QoS Enforced] Running Tenant A + QoS-Throttled Tenant B "
                "(Token-Bucket Paced)..."
            )
            t0_qos = time.perf_counter_ns()
            await asyncio.gather(
                run_tenant_a_oltp(adapter, target_a, tenant_a_ops, collector_a_qos),
                run_tenant_b_noisy_neighbor(
                    adapter, target_b, tenant_b_mb, collector_b_qos, throttle_sleep_sec=0.001
                ),
            )
            qos_duration = max((time.perf_counter_ns() - t0_qos) / 1e9, 1e-9)
            qos_p99 = collector_a_qos.percentile_ms(0.99)
            qos_b_gbps = (collector_b_qos.total_bytes * 8) / qos_duration / 1e9

        is_sla_met = qos_p99 <= sla_threshold_ms
        qos_status = (
            f"PASS (p99 <= {sla_threshold_ms:.1f}ms)" if is_sla_met else "FAIL (QoS VIOLATION)"
        )

        print(
            "\n+--------------------------------------------------------------------------------+"
        )
        print("| MULTI-TENANT QUALITY OF SERVICE (QoS) & CONTENTION AUDIT                       |")
        print("+--------------------------------------------------------------------------------+")
        print(f"| Tenant A Baseline (p99):       {baseline_p99:>16.3f} ms                   |")
        print(f"| Contended Unthrottled (p50):   {contended_p50:>16.3f} ms                   |")
        print(f"| Contended Unthrottled (p99):   {contended_p99:>16.3f} ms                   |")
        print(f"| Contention Jitter Inflation:   {jitter_ratio:>16.2f}x                    |")
        rate_b_str = f"{unthrottled_b_gbps:.2f} Gbps"
        print(f"| Tenant B Unthrottled Rate:     {rate_b_str:>16}                 |")
        print("+--------------------------------------------------------------------------------+")
        if qos_throttle:
            print(f"| QoS-Throttled Tenant A (p99):  {qos_p99:>16.3f} ms                   |")
            rate_qos_b = f"{qos_b_gbps:.2f} Gbps"
            print(f"| QoS-Throttled Tenant B Rate:   {rate_qos_b:>16}                 |")
            print(f"| QoS SLA Compliance Status:     {qos_status:>26}        |")
            print(
                "+--------------------------------------------------------------------------------+"
            )
        print()

        return 0
    finally:
        if cleanup_tmp and tmp_dir is not None:
            with contextlib.suppress(Exception):
                tmp_dir.cleanup()


def main() -> int:
    """Parse CLI options and run multi-tenant QoS simulation."""
    parser = argparse.ArgumentParser(
        description="SETVE Use Case 07: Multi-Tenant QoS & Resource Contention Simulation"
    )
    parser.add_argument(
        "--tenant-a-ops",
        type=int,
        default=1000,
        help="Number of latency-sensitive OLTP operations (default: 1000)",
    )
    parser.add_argument(
        "--tenant-b-mb",
        type=int,
        default=32,
        help="Volume of noisy-neighbor batch payload in MB (default: 32)",
    )
    parser.add_argument(
        "--sla-ms",
        type=float,
        default=2.0,
        help="Target tail latency SLA limit for Tenant A in ms (default: 2.0)",
    )
    parser.add_argument(
        "--target-uri",
        type=str,
        default=None,
        help="Target storage URI (default: temporary storage file)",
    )
    parser.add_argument(
        "--no-qos-throttle",
        action="store_true",
        help="Disable Phase 3 token-bucket QoS throttling audit",
    )
    args = parser.parse_args()

    return asyncio.run(
        run_multitenant_qos_simulation(
            tenant_a_ops=args.tenant_a_ops,
            tenant_b_mb=args.tenant_b_mb,
            target_uri=args.target_uri,
            sla_threshold_ms=args.sla_ms,
            qos_throttle=not args.no_qos_throttle,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
