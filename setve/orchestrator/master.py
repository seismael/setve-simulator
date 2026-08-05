"""Multi-Process Control Plane Master Controller."""

import multiprocessing as mp
import socket
from typing import List

from setve.adapters.factory import AdapterFactory
from setve.orchestrator.affinity import available_cores
from setve.orchestrator.cluster import DeterministicShardGenerator
from setve.orchestrator.worker import run_worker_process
from setve.payload.blueprint import WorkloadBlueprint


class MultiCoreOrchestrator:
    """Master controller that manages core-pinned simulation worker processes."""

    def __init__(self, core_ids: List[int] | None = None) -> None:
        self.core_ids = core_ids or available_cores()
        self.processes: List[mp.Process] = []
        self.node_id = socket.gethostname()

    def start(self, blueprint: WorkloadBlueprint) -> None:
        """Spawn core-pinned worker process fleet using computed shards and blueprint."""
        print(f"Executing blueprint: {blueprint.run_id} on cores: {self.core_ids}")
        
        # Calculate shards for this node
        nodes = [(self.node_id, len(self.core_ids))]
        
        # Convert GB/s to bytes/sec
        target_bps = blueprint.target_throughput_gbps * (1024**3)
        
        shards = DeterministicShardGenerator.generate_cluster_shards(
            global_seed=blueprint.global_seed,
            nodes=nodes,
            target_total_throughput_bps=target_bps,
            block_size=blueprint.block_size_bytes,
        )
        
        local_shards = shards.get(self.node_id, [])
        adapter_cls = AdapterFactory.get_adapter_class(blueprint.target_uri)

        for i in range(len(self.core_ids)):
            if i >= len(local_shards):
                break
                
            shard_spec = local_shards[i]
            p = mp.Process(
                target=run_worker_process,
                args=(shard_spec, blueprint.target_uri, adapter_cls, blueprint.duration_seconds),
                daemon=True,
            )
            p.start()
            self.processes.append(p)

        for p in self.processes:
            p.join()


def main() -> None:
    """CLI entrypoint for SETVE simulation orchestrator."""
    print("SETVE Orchestrator CLI v0.2.0")
    
    # In production, this would be loaded from YAML/JSON
    blueprint = WorkloadBlueprint.from_dict({
        "run_id": "test-run-1",
        "target_uri": "file://sim_output",
        "block_size_bytes": 1048576,
        "entropy_ratio": 0.85,
        "target_throughput_gbps": 10,
        "duration_seconds": 2,
        "global_seed": 9999
    })
    
    orchestrator = MultiCoreOrchestrator()
    orchestrator.start(blueprint)


if __name__ == "__main__":
    main()
