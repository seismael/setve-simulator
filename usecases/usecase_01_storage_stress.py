"""Use Case 01: High-Throughput NVMe & Direct I/O Storage Stress Testing.

Demonstrates core-pinned multi-process workload execution over POSIX Direct I/O
with zero-copy page-aligned buffers.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
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
        print(f"[*] No target URI specified. Using temporary file: {target_path}")
    else:
        print(f"[*] Target URI: posix://{target_path}")

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
        print(f"[*] Launching {num_cores} worker processes (Cores: {core_ids})...")
        print(f"[*] Block: {block_size_bytes}B | Target: {target_throughput_gbps} Gbps")

        orchestrator = MultiCoreOrchestrator(core_ids=core_ids)
        summary = orchestrator.start(blueprint)

        print("\n" + summary.format_table())
        print("[*] Completed successfully.")
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

    args = parser.parse_args()
    return run_storage_stress(
        target_path=args.target,
        block_size_bytes=args.block_size,
        target_throughput_gbps=args.throughput,
        duration_seconds=args.duration,
        entropy_ratio=args.entropy,
        num_cores=args.cores,
    )


if __name__ == "__main__":
    sys.exit(main())
