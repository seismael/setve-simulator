"""Extended Unit Tests for DeterministicShardGenerator under Heterogeneous & Boundary Topologies."""

import pytest

from steve.orchestrator.cluster import DeterministicShardGenerator, WorkerShardSpec


def test_sharding_heterogeneous_and_prime_cores() -> None:
    """Verify cluster sharding across prime-numbered core counts and heterogeneous topologies."""
    # Heterogeneous nodes: node-0 (7 cores), node-1 (3 cores), node-2 (13 cores)
    nodes = [("node-0", 7), ("node-1", 3), ("node-2", 13)]
    target_throughput_bps = 23 * 1024 * 1024 * 1024
    block_size = 65536  # 64KB

    shards_map = DeterministicShardGenerator.generate_cluster_shards(
        global_seed=12345,
        nodes=nodes,
        target_total_throughput_bps=target_throughput_bps,
        block_size=block_size,
    )

    all_shards = [s for sublist in shards_map.values() for s in sublist]
    assert len(all_shards) == 23

    # Validate each shard properties
    offsets: set[int] = set()
    seeds: set[int] = set()
    total_bps = 0

    for s in all_shards:
        assert isinstance(s, WorkerShardSpec)
        assert s.block_size_bytes == block_size
        assert s.base_offset_bytes % block_size == 0
        offsets.add(s.base_offset_bytes)
        seeds.add(s.seed)
        total_bps += s.target_throughput_bps

    # All base offsets must be unique and perfectly disjoint
    assert len(offsets) == 23
    # All pseudo-random seeds must be uniquely generated via SplitMix64
    assert len(seeds) == 23
    # Total assigned throughput must match cluster target
    assert pytest.approx(total_bps, rel=1e-5) == target_throughput_bps


def test_sharding_single_node_single_core() -> None:
    """Verify single-node single-core boundary condition."""
    shards_map = DeterministicShardGenerator.generate_cluster_shards(
        global_seed=999,
        nodes=[("single-node", 1)],
        target_total_throughput_bps=10 * 1024 * 1024 * 1024,
        block_size=4096,
    )

    assert "single-node" in shards_map
    shards = shards_map["single-node"]
    assert len(shards) == 1
    s = shards[0]
    assert s.node_id == "single-node"
    assert s.core_id == 0
    assert s.base_offset_bytes == 0
    assert s.stride_bytes == 4096
    assert s.target_throughput_bps == 10 * 1024 * 1024 * 1024
