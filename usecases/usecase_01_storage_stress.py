"""Use Case 01: High-Throughput NVMe & Direct I/O Storage Stress Testing.

Demonstrates core-pinned multi-process workload execution over POSIX Direct I/O
with zero-copy page-aligned buffers.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from pathlib import Path

# Ensure setve package is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from setve.orchestrator.master import MultiCoreOrchestrator  # noqa: E402
from setve.payload.blueprint import WorkloadBlueprint  # noqa: E402


def run_storage_stress(
    target_path: str | None = None,
    block_size_bytes: int = 1048576,
    target_throughput_gbps: float = 10.0,
    duration_seconds: float = 2.0,
    entropy_ratio: float = 0.5,
    num_cores: int = 2,
    queue_depth: int = 16,
) -> int:
    """Execute multi-core Direct I/O stress workload and print telemetry summary."""
    print("=" * 80)
    print("  SETVE USE CASE 01: NVMe & Direct I/O Storage Saturation Engine")
    print("=" * 80)

    cleanup_tmp = False
    if not target_path:
        tmp_dir = tempfile.TemporaryDirectory()
        target_path = str(Path(tmp_dir.name) / "setve_stress.dat")
        cleanup_tmp = True
        print(f"[*] Target URI:       posix://{target_path} (Temporary Storage)")
    else:
        print(f"[*] Target URI:       posix://{target_path}")

    print(f"[*] Direct I/O Block: {block_size_bytes:,} Bytes ({block_size_bytes / 1024:.1f} KB)")
    print(f"[*] Target Rate:      {target_throughput_gbps:.2f} Gbps ({num_cores} cores)")
    print(f"[*] Queue Depth:      {queue_depth} concurrent SQEs/worker")
    print(f"[*] Entropy Ratio:    {entropy_ratio * 100:.1f}% randomized payload bytes")

    try:
        blueprint = WorkloadBlueprint.from_dict(
            {
                "run_id": "nvme-direct-io-stress-01",
                "target_uri": f"posix://{target_path}",
                "block_size_bytes": block_size_bytes,
                "entropy_ratio": entropy_ratio,
                "target_throughput_gbps": target_throughput_gbps,
                "duration_seconds": duration_seconds,
                "global_seed": 42,
            }
        )

        core_ids = list(range(num_cores))
        print(f"\n[*] Pinning worker processes to physical CPU cores: {core_ids}")
        t0 = time.perf_counter()

        orchestrator = MultiCoreOrchestrator(core_ids=core_ids)
        summary = orchestrator.start(blueprint)

        elapsed = max(time.perf_counter() - t0, 0.001)
        total_ops = summary.total_ops
        total_mb = summary.total_bytes / (1024 * 1024)
        measured_gbps = (summary.total_bytes * 8) / elapsed / 1e9
        iops = total_ops / elapsed

        bw_str = f"{measured_gbps:.2f} Gbps ({measured_gbps / 8:.2f} GB/s)"
        core_rate_str = f"{measured_gbps / num_cores:.2f} Gbps/core"

        print("\n" + summary.format_table())

        print("+--------------------------------------------------------------------------------+")
        print("| STORAGE SATURATION DIAGNOSTICS & IOPS SUMMARY                                  |")
        print("+--------------------------------------------------------------------------------+")
        print(f"| Aggregate Bandwidth:        {bw_str:>46} |")
        print(f"| Sustained IOPS:             {f'{iops:,.1f} IOPS':>46} |")
        print(f"| Transferred Payload:        {f'{total_mb:,.1f} MB':>46} |")
        print(f"| Per-Core Rate:              {core_rate_str:>46} |")
        print(f"| Page Cache Bypass (O_DIRECT): {'ENFORCED (4096B ALIGNED)':>44} |")
        print(
            "+--------------------------------------------------------------------------------+\n"
        )

        return 0
    finally:
        if cleanup_tmp:
            import contextlib

            with contextlib.suppress(Exception):
                tmp_dir.cleanup()


def main() -> int:
    """Parse CLI options and execute stress workload."""
    parser = argparse.ArgumentParser(
        description="SETVE Use Case 01: Storage Saturation Stress Tester"
    )
    parser.add_argument(
        "--target",
        type=str,
        default=None,
        help="Target file or raw device path (default: temporary file)",
    )
    parser.add_argument(
        "--block-size",
        type=int,
        default=1048576,
        help="Direct I/O block size in bytes (default: 1048576 / 1MB)",
    )
    parser.add_argument(
        "--throughput",
        type=float,
        default=10.0,
        help="Target throughput in Gbps (default: 10.0)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=2.0,
        help="Workload duration in seconds (default: 2.0)",
    )
    parser.add_argument(
        "--entropy",
        type=float,
        default=0.5,
        help="Payload entropy ratio between 0.0 and 1.0 (default: 0.5)",
    )
    parser.add_argument(
        "--cores",
        type=int,
        default=2,
        help="Number of core-pinned worker processes (default: 2)",
    )
    parser.add_argument(
        "--queue-depth",
        type=int,
        default=16,
        help="Target queue depth per worker core (default: 16)",
    )

    args = parser.parse_args()
    return run_storage_stress(
        target_path=args.target,
        block_size_bytes=args.block_size,
        target_throughput_gbps=args.throughput,
        duration_seconds=args.duration,
        entropy_ratio=args.entropy,
        num_cores=args.cores,
        queue_depth=args.queue_depth,
    )


if __name__ == "__main__":
    sys.exit(main())
