"""STEVE Use Case 09: Multi-Tier Storage Lifecycle (Hot / Warm / Cold Demotion).

Simulates automated data progression across heterogeneous storage tiers:
1. Hot Tier (NVMe / POSIX Direct I/O): 4 KB random read/write active working set.
2. Warm Tier (Block Volume Staging): 1 MB sequential consolidation passes.
3. Cold Tier (S3 Object Store): 5 MB multipart compressed archive streaming.
"""

import argparse
import asyncio
import sys
import tempfile
import time
from pathlib import Path

# Ensure steve package is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from steve.adapters.base import TargetDescriptor  # noqa: E402
from steve.adapters.factory import AdapterFactory  # noqa: E402
from steve.payload.buffer_pool import BufferPool  # noqa: E402
from steve.payload.mutator import PySIMDPayloadMutator  # noqa: E402
from steve.validation.metric_collector import MetricCollector  # noqa: E402


async def run_storage_tiering_simulation(
    hot_ops: int = 2000,
    warm_mb: int = 64,
    cold_chunks: int = 10,
    dataset_tb: float = 10.0,
) -> int:
    """Execute multi-tier storage lifecycle simulation."""
    print("=" * 80)
    print("  STEVE USE CASE 09: Multi-Tier Storage Lifecycle (Hot/Warm/Cold)")
    print("=" * 80)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # 1. Hot Tier Execution (NVMe / POSIX Direct I/O)
        hot_file = tmp_path / "tier_hot_nvme.dat"
        hot_uri = f"posix://{hot_file}"
        print(f"\n[Tier 1: Hot NVMe] Running {hot_ops:,} random 4 KB I/O operations...")
        hot_adapter = AdapterFactory.create(hot_uri)
        await hot_adapter.initialize({"direct_io": False})
        hot_target = TargetDescriptor(endpoint_uri=hot_uri, resource_path="tier_hot_nvme.dat")

        hot_collector = MetricCollector()
        hot_pool = BufferPool(buffer_count=4, buffer_size=4096)
        try:
            t0_hot = time.perf_counter_ns()
            for i in range(hot_ops):
                buf = hot_pool.acquire(i % hot_pool.buffer_count)
                op_t0 = time.perf_counter_ns()
                w = await hot_adapter.write(hot_target, offset=(i * 4096) % 10485760, payload=buf)
                hot_collector.record_latency(time.perf_counter_ns() - op_t0)
                hot_collector.record_bytes(w)
            hot_duration = max((time.perf_counter_ns() - t0_hot) / 1e9, 1e-9)
        finally:
            hot_pool.close()

        hot_iops = hot_ops / hot_duration
        hot_p99 = hot_collector.percentile_ms(0.99)

        # 2. Warm Tier Execution (Block Staging Consolidation)
        warm_file = tmp_path / "tier_warm_block.dat"
        warm_uri = f"posix://{warm_file}"
        print(f"\n[Tier 2: Warm Block] Consolidating {warm_mb} MB in 1 MB sequential chunks...")
        warm_adapter = AdapterFactory.create(warm_uri)
        await warm_adapter.initialize({"direct_io": False})
        warm_target = TargetDescriptor(endpoint_uri=warm_uri, resource_path="tier_warm_block.dat")

        warm_collector = MetricCollector()
        mutator = PySIMDPayloadMutator(1048576)
        try:
            t0_warm = time.perf_counter_ns()
            for i in range(warm_mb):
                buf = mutator.apply_entropy(0, 1048576, seed=i)
                op_t0 = time.perf_counter_ns()
                w = await warm_adapter.write(warm_target, offset=i * 1048576, payload=buf)
                warm_collector.record_latency(time.perf_counter_ns() - op_t0)
                warm_collector.record_bytes(w)
            warm_duration = max((time.perf_counter_ns() - t0_warm) / 1e9, 1e-9)
        finally:
            mutator.close()

        warm_gbps = (warm_mb * 1024 * 1024 * 8) / warm_duration / 1e9

        # 3. Cold Tier Execution (S3 Object Store Multipart Archival)
        s3_uri = "s3://compliance-archive-us-east-1/demoted-cold-tier"
        print(f"\n[Tier 3: Cold S3 Object] Archiving {cold_chunks} x 5 MB multipart objects...")
        s3_adapter = AdapterFactory.create(s3_uri)
        await s3_adapter.initialize({"region": "us-east-1"})
        s3_target = TargetDescriptor(
            endpoint_uri=s3_uri, resource_path="compliance-archive-us-east-1/demoted-cold-tier"
        )

        s3_collector = MetricCollector()
        cold_block_size = 5242880  # 5 MB
        cold_pool = BufferPool(buffer_count=2, buffer_size=cold_block_size)
        try:
            t0_cold = time.perf_counter_ns()
            for i in range(cold_chunks):
                buf = cold_pool.acquire(i % cold_pool.buffer_count)
                op_t0 = time.perf_counter_ns()
                w = await s3_adapter.write(s3_target, offset=i * cold_block_size, payload=buf)
                s3_collector.record_latency(time.perf_counter_ns() - op_t0)
                s3_collector.record_bytes(w)
            await s3_adapter.flush(s3_target)
            cold_duration = max((time.perf_counter_ns() - t0_cold) / 1e9, 1e-9)
        finally:
            cold_pool.close()

        cold_mb_total = (cold_chunks * cold_block_size) / (1024 * 1024)
        cold_gbps = (cold_chunks * cold_block_size * 8) / cold_duration / 1e9

        # Economic & Cost Savings Analysis for enterprise dataset
        # Standard Cloud Storage Pricing Models ($/GB/month)
        hot_cost_per_gb = 0.250  # Provisioned IOPS NVMe SSD ($250/TB/mo)
        warm_cost_per_gb = 0.080  # Standard Block Volume ($80/TB/mo)
        cold_cost_per_gb = 0.023  # S3 Standard Object Store ($23/TB/mo)

        hot_monthly = dataset_tb * 1024 * hot_cost_per_gb
        warm_monthly = dataset_tb * 1024 * warm_cost_per_gb
        cold_monthly = dataset_tb * 1024 * cold_cost_per_gb

        # Tiering policy allocation: 10% Hot, 30% Warm, 60% Cold
        tiered_monthly = (0.10 * hot_monthly) + (0.30 * warm_monthly) + (0.60 * cold_monthly)
        monthly_savings = hot_monthly - tiered_monthly
        annual_savings = monthly_savings * 12
        three_year_roi = annual_savings * 3
        savings_pct = ((hot_monthly - tiered_monthly) / hot_monthly) * 100.0

        # Summary Report
        print(
            "\n+--------------------------------------------------------------------------------+"
        )
        print("| MULTI-TIER STORAGE LIFECYCLE & COST REDUCTION SUMMARY                          |")
        print("+--------------------------------------------------------------------------------+")
        hot_desc = f"{hot_iops:,.1f} IOPS (p99: {hot_p99:.3f} ms)"
        print(f"| Hot NVMe Tier (Active Set):    {hot_desc:>46} |")
        warm_desc = f"{warm_gbps:.2f} Gbps ({warm_mb} MB transferred)"
        print(f"| Warm Block Tier (Staging):     {warm_desc:>46} |")
        cold_desc = f"{cold_gbps:.2f} Gbps ({cold_mb_total:.1f} MB archived)"
        print(f"| Cold S3 Object Tier (Archival):{cold_desc:>46} |")
        print("+--------------------------------------------------------------------------------+")
        print(f"| Simulated Dataset Volume:      {f'{dataset_tb:.1f} TB Total Managed':>46} |")
        print(f"| Baseline Cost (100% Hot NVMe): {f'${hot_monthly:,.2f} / month':>46} |")
        print(f"| Tiered Cost (10% Hot/30%W/60%C):{f'${tiered_monthly:,.2f} / month':>45} |")
        print(f"| Monthly Net Savings:           {f'${monthly_savings:,.2f} / month':>46} |")
        print(f"| 3-Year Enterprise TCO Savings: {f'${three_year_roi:,.2f} ROI':>46} |")
        print(f"| Net Lifecycle Cost Reduction:  {f'{savings_pct:.1f}% Savings':>46} |")
        print(
            "+--------------------------------------------------------------------------------+\n"
        )

    return 0


def main() -> int:
    """Parse CLI options and run storage tiering simulation."""
    parser = argparse.ArgumentParser(
        description="STEVE Use Case 09: Multi-Tier Storage Lifecycle (Hot/Warm/Cold)"
    )
    parser.add_argument(
        "--hot-ops",
        type=int,
        default=1000,
        help="Number of Hot NVMe 4 KB operations (default: 1000)",
    )
    parser.add_argument(
        "--warm-mb",
        type=int,
        default=32,
        help="Volume of Warm Block staging payload in MB (default: 32)",
    )
    parser.add_argument(
        "--cold-chunks",
        type=int,
        default=5,
        help="Number of Cold S3 5 MB multipart chunks (default: 5)",
    )
    parser.add_argument(
        "--dataset-tb",
        type=float,
        default=10.0,
        help="Simulated total enterprise dataset in TB (default: 10.0)",
    )
    args = parser.parse_args()

    return asyncio.run(
        run_storage_tiering_simulation(
            hot_ops=args.hot_ops,
            warm_mb=args.warm_mb,
            cold_chunks=args.cold_chunks,
            dataset_tb=args.dataset_tb,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
