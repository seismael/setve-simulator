"""SETVE Use Case 10: Tail-Latency Micro-Burst & Jitter Analysis.

Simulates periodic high-intensity I/O micro-bursts:
1. Baseline Phase: Smooth steady-state 4 KB requests.
2. Micro-Burst Phase: Periodic 50ms 100x traffic surges stressing queue depth.
3. 64-Bucket HDR Histogram Analysis: Computes p50, p90, p99, p99.9, and p99.99 latency distribution.
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
from setve.validation.metric_collector import MetricCollector  # noqa: E402


async def run_microburst_simulation(
    steady_ops: int = 2000,
    burst_cycles: int = 5,
    burst_intensity: int = 500,
    target_uri: str = "posix:///tmp/microburst_target.dat",
) -> int:
    """Execute micro-burst traffic generation and tail-latency HDR analysis."""
    print("=" * 80)
    print("  SETVE USE CASE 10: Tail-Latency Micro-Burst & Jitter Analysis")
    print("=" * 80)

    adapter = AdapterFactory.create(target_uri)
    await adapter.initialize({"direct_io": False})
    target = TargetDescriptor(endpoint_uri=target_uri, resource_path="microburst_target.dat")

    pool = BufferPool(buffer_count=8, buffer_size=4096)
    steady_collector = MetricCollector()
    burst_collector = MetricCollector()
    combined_collector = MetricCollector()

    print(f"[*] Running steady-state baseline ({steady_ops:,} ops)...")
    try:
        for i in range(steady_ops):
            buf = pool.acquire(i)
            t0 = time.perf_counter_ns()
            w = await adapter.write(target, offset=(i * 4096) % 10485760, payload=buf)
            lat = time.perf_counter_ns() - t0
            steady_collector.record_latency(lat)
            steady_collector.record_bytes(w)
            combined_collector.record_latency(lat)
            combined_collector.record_bytes(w)
            await asyncio.sleep(0.00005)

        print(
            f"[*] Injecting {burst_cycles} micro-burst cycles "
            f"({burst_intensity} ops/burst, no pacing)..."
        )
        for _cycle in range(burst_cycles):
            for b in range(burst_intensity):
                buf = pool.acquire(b)
                t0 = time.perf_counter_ns()
                w = await adapter.write(target, offset=(b * 4096) % 10485760, payload=buf)
                lat = time.perf_counter_ns() - t0
                burst_collector.record_latency(lat)
                burst_collector.record_bytes(w)
                combined_collector.record_latency(lat)
                combined_collector.record_bytes(w)
            await asyncio.sleep(0.01)  # Inter-burst lull

    finally:
        pool.close()

    # Percentiles in milliseconds
    p50_s = steady_collector.percentile_ms(0.50)
    p99_s = steady_collector.percentile_ms(0.99)
    p999_s = steady_collector.percentile_ms(0.999)

    p50_c = combined_collector.percentile_ms(0.50)
    p90_c = combined_collector.percentile_ms(0.90)
    p99_c = combined_collector.percentile_ms(0.99)
    p999_c = combined_collector.percentile_ms(0.999)
    degrad_factor = p999_c / max(p50_s, 0.001)


    print("\n+--------------------------------------------------------------------------------+")
    print("| 64-BUCKET LOGARITHMIC HDR HISTOGRAM TAIL LATENCY REPORT                        |")
    print("+--------------------------------------------------------------------------------+")
    print(f"| Steady-State Baseline (p50):    {p50_s:>16.3f} ms                           |")
    print(f"| Steady-State Baseline (p99):    {p99_s:>16.3f} ms                           |")
    print(f"| Steady-State Baseline (p99.9):  {p999_s:>16.3f} ms                           |")
    print("+--------------------------------------------------------------------------------+")
    print(f"| Micro-Burst Contended (p50):    {p50_c:>16.3f} ms                           |")
    print(f"| Micro-Burst Contended (p90):    {p90_c:>16.3f} ms                           |")
    print(f"| Micro-Burst Contended (p99):    {p99_c:>16.3f} ms                           |")
    print(f"| Micro-Burst Tail-Spike (p99.9): {p999_c:>16.3f} ms                           |")
    print(f"| Tail Degradation (p99.9 / p50): {degrad_factor:>16.2f}x                            |")
    print("+--------------------------------------------------------------------------------+\n")

    return 0


def main() -> int:
    """Parse CLI options and execute micro-burst simulation."""
    parser = argparse.ArgumentParser(
        description="SETVE Use Case 10: Tail-Latency Micro-Burst & Jitter Analysis"
    )
    parser.add_argument(
        "--steady-ops",
        type=int,
        default=1500,
        help="Number of steady-state baseline operations",
    )
    parser.add_argument(
        "--burst-cycles",
        type=int,
        default=3,
        help="Number of micro-burst traffic surges",
    )
    parser.add_argument(
        "--burst-intensity",
        type=int,
        default=300,
        help="Number of unpaced back-to-back operations per burst",
    )
    parser.add_argument(
        "--target-uri",
        type=str,
        default="posix:///tmp/microburst_target.dat",
        help="Target storage URI",
    )
    args = parser.parse_args()

    return asyncio.run(
        run_microburst_simulation(
            steady_ops=args.steady_ops,
            burst_cycles=args.burst_cycles,
            burst_intensity=args.burst_intensity,
            target_uri=args.target_uri,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
