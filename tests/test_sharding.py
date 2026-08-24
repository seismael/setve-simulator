"""Tests for DeterministicShardGenerator partitioning and seed calculation."""

from steve.orchestrator.cluster import DeterministicShardGenerator


def test_deterministic_sharding_distribution() -> None:
    """Verify sharding calculates non-overlapping base offsets and equal throughput."""
    nodes = [("node-0", 4), ("node-1", 4)]
    target_bps = 800 * (1024**3)  # 800 GB/s

    shards = DeterministicShardGenerator.generate_cluster_shards(
        global_seed=42,
        nodes=nodes,
        target_total_throughput_bps=target_bps,
        block_size=1048576,
    )

    assert "node-0" in shards
    assert "node-1" in shards
    assert len(shards["node-0"]) == 4
    assert len(shards["node-1"]) == 4

    total_shards = shards["node-0"] + shards["node-1"]
    assert len(total_shards) == 8

    # All per-core throughput targets should match total_bps / 8
    expected_per_core_bps = target_bps // 8
    for shard in total_shards:
        assert shard.target_throughput_bps == expected_per_core_bps
        assert shard.stride_bytes == 8 * 1048576
        assert shard.block_size_bytes == 1048576

    # Verify all base offsets are unique and non-overlapping
    base_offsets = [s.base_offset_bytes for s in total_shards]
    assert len(set(base_offsets)) == 8
    assert base_offsets == [i * 1048576 for i in range(8)]

    # Verify all seeds are deterministic and non-zero
    seeds = [s.seed for s in total_shards]
    assert len(set(seeds)) == 8
    for seed in seeds:
        assert seed != 0
