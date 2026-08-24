"""Deterministic cluster sharding engine."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WorkerShardSpec:
    node_id: str
    core_id: int
    seed: int
    base_offset_bytes: int
    stride_bytes: int
    block_size_bytes: int
    target_throughput_bps: int


class DeterministicShardGenerator:
    """Calculates non-overlapping payload seeds and block offsets per core worker."""

    @staticmethod
    def _splitmix64(state: int) -> int:
        """64-bit deterministic SplitMix hash function."""
        z = (state + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF
        return (z ^ (z >> 31)) & 0xFFFFFFFFFFFFFFFF

    @classmethod
    def generate_cluster_shards(
        cls,
        global_seed: int,
        nodes: list[tuple[str, int]],
        target_total_throughput_bps: int,
        block_size: int = 1048576,
    ) -> dict[str, list[WorkerShardSpec]]:
        """Generates deterministic worker shard configurations across all physical nodes."""
        total_cores = sum(cores for _, cores in nodes)
        per_core_throughput = target_total_throughput_bps // total_cores if total_cores else 0

        shards: dict[str, list[WorkerShardSpec]] = {}
        global_core_index = 0

        for node_id, core_count in nodes:
            node_shards: list[WorkerShardSpec] = []
            for local_core in range(core_count):
                combined_state = (global_seed ^ global_core_index) & 0xFFFFFFFFFFFFFFFF
                worker_seed = cls._splitmix64(combined_state)
                base_offset = global_core_index * block_size
                stride = total_cores * block_size

                spec = WorkerShardSpec(
                    node_id=node_id,
                    core_id=local_core,
                    seed=worker_seed,
                    base_offset_bytes=base_offset,
                    stride_bytes=stride,
                    block_size_bytes=block_size,
                    target_throughput_bps=per_core_throughput,
                )
                node_shards.append(spec)
                global_core_index += 1

            shards[node_id] = node_shards

        return shards
