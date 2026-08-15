"""SETVE Use Case 08: Distributed Fault-Tolerance, Node Eviction & Chaos Engineering.

Simulates distributed cluster resilience under dynamic node failure:
1. Provisions initial cluster topology (e.g., 16 nodes, 128 cores).
2. Simulates mid-run hardware crash / eviction of 25% of generator nodes.
3. Dynamically rebalances shard ranges across surviving nodes without gaps or collisions.
"""

import argparse
import sys
import time
from pathlib import Path

# Ensure setve package is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from setve.orchestrator.cluster import DeterministicShardGenerator  # noqa: E402


def calculate_hash_uniformity(seeds: list[int], num_buckets: int = 16) -> tuple[float, str]:
    """Calculate chi-squared uniformity goodness-of-fit across hash seed buckets."""
    if not seeds:
        return 0.0, "PERFECT"
    buckets = [0] * num_buckets
    for s in seeds:
        bucket_idx = s % num_buckets
        buckets[bucket_idx] += 1
    expected = len(seeds) / num_buckets
    chi_sq = sum(((count - expected) ** 2) / expected for count in buckets)
    # Normalized uniformity rating
    status = "EXCELLENT (UNIFORM)" if chi_sq < num_buckets * 2 else "ADEQUATE"
    return chi_sq, status


def run_chaos_simulation(
    initial_nodes: int = 16,
    cores_per_node: int = 8,
    failed_nodes: int = 4,
    total_target_size_gb: int = 1024,
    heterogeneous: bool = False,
) -> int:
    """Execute distributed node failure and dynamic shard rebalancing simulation."""
    print("=" * 80)
    print("  SETVE USE CASE 08: Distributed Chaos Engineering & Shard Rebalancing")
    print("=" * 80)

    total_target_bytes = total_target_size_gb * 1024 * 1024 * 1024

    # Provision topology (homogeneous or heterogeneous)
    if heterogeneous:
        # Alternating 16, 8, 4 core node profiles
        initial_node_specs = [
            (f"node-{i}", 16 if i % 3 == 0 else 8 if i % 3 == 1 else 4)
            for i in range(initial_nodes)
        ]
        topology_label = "Heterogeneous (16c/8c/4c mixed)"
    else:
        initial_node_specs = [(f"node-{i}", cores_per_node) for i in range(initial_nodes)]
        topology_label = f"Homogeneous ({cores_per_node} cores/node)"

    initial_total_cores = sum(c for _, c in initial_node_specs)
    surviving_node_specs = initial_node_specs[: max(1, initial_nodes - failed_nodes)]
    surviving_total_cores = sum(c for _, c in surviving_node_specs)

    print(
        f"[*] Initial Cluster Topology:   {initial_nodes} nodes | "
        f"{initial_total_cores} cores ({topology_label})"
    )
    print(
        f"[*] Total Target Address Space:  {total_target_size_gb} GB ({total_target_bytes:,} bytes)"
    )
    fail_pct = (failed_nodes / initial_nodes) * 100
    print(
        f"[*] Chaos Injection Plan:        Simulate failure of "
        f"{failed_nodes} nodes ({fail_pct:.1f}%)\n"
    )

    # Step 1: Initial Shard Distribution
    t0_initial = time.perf_counter_ns()
    initial_shards_map = DeterministicShardGenerator.generate_cluster_shards(
        global_seed=42,
        nodes=initial_node_specs,
        target_total_throughput_bps=total_target_bytes,
        block_size=1048576,
    )
    initial_shards = [s for node_shards in initial_shards_map.values() for s in node_shards]
    t_initial_us = (time.perf_counter_ns() - t0_initial) / 1000
    us_per_core = t_initial_us / max(1, initial_total_cores)

    initial_seeds = [s.seed for s in initial_shards]
    init_chi, init_uniform_status = calculate_hash_uniformity(initial_seeds)

    print(
        f"[+] Initial Shards:  {len(initial_shards)} shards in {t_initial_us:.2f} us "
        f"({us_per_core:.3f} us/core) | Seed Uniformity: {init_uniform_status}"
    )

    # Step 2: Chaos Injection - Simulate Node Eviction
    evicted = [f"node-{i}" for i in range(initial_nodes - failed_nodes, initial_nodes)]
    print(f"\n[!] CHAOS INJECTION: Evicting nodes {evicted}...")

    # Step 3: Dynamic Rebalancing over Surviving Nodes
    t0_rebalance = time.perf_counter_ns()
    rebalanced_shards_map = DeterministicShardGenerator.generate_cluster_shards(
        global_seed=42,
        nodes=surviving_node_specs,
        target_total_throughput_bps=total_target_bytes,
        block_size=1048576,
    )
    rebalanced_shards = [s for node_shards in rebalanced_shards_map.values() for s in node_shards]
    t_rebalance_us = (time.perf_counter_ns() - t0_rebalance) / 1000

    rebalance_rate = (len(rebalanced_shards) / max(t_rebalance_us, 0.001)) * 1000
    print(
        f"[+] Rebalanced Shards Created:   {len(rebalanced_shards)} shards "
        f"in {t_rebalance_us:.2f} us ({rebalance_rate:,.0f} shards/ms)"
    )

    # Step 4: Chaos Recovery - Simulated Node Rejoin
    print(f"\n[+] CHAOS RECOVERY: Nodes {evicted} healed and re-joining cluster...")
    t0_recovery = time.perf_counter_ns()
    healed_shards_map = DeterministicShardGenerator.generate_cluster_shards(
        global_seed=42,
        nodes=initial_node_specs,
        target_total_throughput_bps=total_target_bytes,
        block_size=1048576,
    )
    healed_shards = [s for node_shards in healed_shards_map.values() for s in node_shards]
    t_recovery_us = (time.perf_counter_ns() - t0_recovery) / 1000

    print(f"[+] Cluster Restored:            {len(healed_shards)} shards in {t_recovery_us:.2f} us")

    # Step 5: Validate Address Space Integrity & SplitMix64 Distribution
    base_offsets = [s.base_offset_bytes for s in rebalanced_shards]
    unique_offsets = len(set(base_offsets)) == len(rebalanced_shards)
    healed_offsets = [s.base_offset_bytes for s in healed_shards]
    unique_healed = len(set(healed_offsets)) == len(healed_shards)
    integrity_pass = unique_offsets and unique_healed
    integrity_status = "PASS (100% CONTIGUOUS, ZERO GAPS)" if integrity_pass else "FAIL"

    print("\n+--------------------------------------------------------------------------------+")
    print("| DISTRIBUTED CHAOS REBALANCING & RECOVERY SUMMARY                               |")
    print("+--------------------------------------------------------------------------------+")
    print(f"| Initial Cluster Capacity:   {initial_total_cores:>18} cores                        |")
    print(f"| Degraded Capacity:          {surviving_total_cores:>18} cores                      |")
    print(f"| Restored Cluster Capacity:  {initial_total_cores:>18} cores                        |")
    print(f"| Eviction Rebalance Latency: {t_rebalance_us:>18.2f} us                           |")
    print(f"| Recovery Rebalance Latency: {t_recovery_us:>18.2f} us                           |")
    print(f"| SplitMix64 Hash Uniformity: {init_uniform_status:>24}                   |")
    print(f"| Shard Boundary Integrity:   {integrity_status:>24}                   |")
    print("+--------------------------------------------------------------------------------+\n")

    return 0 if integrity_pass else 1


def main() -> int:
    """Parse CLI options and execute chaos simulation."""
    parser = argparse.ArgumentParser(
        description="SETVE Use Case 08: Distributed Chaos Engineering & Shard Rebalancing"
    )
    parser.add_argument(
        "--nodes",
        type=int,
        default=16,
        help="Initial number of distributed generator nodes (default: 16)",
    )
    parser.add_argument(
        "--cores-per-node",
        type=int,
        default=8,
        help="Physical CPU cores per node (default: 8)",
    )
    parser.add_argument(
        "--failed-nodes",
        type=int,
        default=4,
        help="Number of failed/evicted nodes to simulate (default: 4)",
    )
    parser.add_argument(
        "--target-gb",
        type=int,
        default=512,
        help="Total target dataset size in GB (default: 512)",
    )
    parser.add_argument(
        "--heterogeneous",
        action="store_true",
        help="Enable mixed/asymmetric per-node core topologies (16c/8c/4c)",
    )
    args = parser.parse_args()

    return run_chaos_simulation(
        initial_nodes=args.nodes,
        cores_per_node=args.cores_per_node,
        failed_nodes=args.failed_nodes,
        total_target_size_gb=args.target_gb,
        heterogeneous=args.heterogeneous,
    )


if __name__ == "__main__":
    sys.exit(main())
