"""Local Multi-Node Distributed Cluster Emulation Runner."""

from __future__ import annotations

import argparse
import asyncio
import multiprocessing as mp
import os
import tempfile
import time

from setve.logging import configure_logging, get_logger
from setve.orchestrator.cluster import DeterministicShardGenerator, WorkerShardSpec
from setve.orchestrator.sync import ClusterSyncServicer
from setve.payload.mutator import PySIMDPayloadMutator
from setve.validation.metric_collector import MetricCollector
from setve.validation.reporter import ClusterTelemetrySummary, WorkerTelemetryResult


def run_simulated_node_worker(
    node_id: str,
    core_id: int,
    shard_spec: WorkerShardSpec,
    target_path: str,
    duration_sec: float,
    result_queue: mp.Queue[WorkerTelemetryResult],
) -> None:
    """Simulates a core-pinned worker executing on a named cluster node."""
    logger = get_logger("setve.node.worker", node_id=node_id, core_id=core_id)
    collector = MetricCollector()
    mutator = PySIMDPayloadMutator(buffer_size=shard_spec.block_size_bytes)

    node_file = f"{target_path}_{node_id}_core_{core_id}.dat"
    fd = os.open(node_file, os.O_RDWR | os.O_CREAT | getattr(os, "O_BINARY", 0), 0o666)

    offset = shard_spec.base_offset_bytes
    stride = shard_spec.stride_bytes
    block_size = shard_spec.block_size_bytes

    t_start = time.perf_counter()
    ops = 0
    total_bytes = 0

    try:
        t_end = t_start + duration_sec
        while time.perf_counter() < t_end:
            t0 = time.perf_counter_ns()
            buf = mutator.apply_entropy(0, block_size, shard_spec.seed + ops)
            os.lseek(fd, offset, os.SEEK_SET)
            written = os.write(fd, buf.view)
            elapsed_ns = time.perf_counter_ns() - t0

            collector.record_latency(elapsed_ns)
            collector.record_bytes(written)
            offset += stride
            ops += 1
            total_bytes += written
    finally:
        mutator.close()
        os.close(fd)

    actual_duration = max(time.perf_counter() - t_start, 1e-6)
    result = WorkerTelemetryResult(
        core_id=core_id,
        node_id=node_id,
        total_ops=collector.total_ops,
        total_bytes=collector.total_bytes,
        duration_sec=actual_duration,
        p50_ms=collector.p50_latency_ms(),
        p90_ms=collector.p90_latency_ms(),
        p99_ms=collector.p99_latency_ms(),
        p999_ms=collector.p999_latency_ms(),
        throughput_gbps=collector.throughput_gbps(actual_duration),
    )
    result_queue.put(result)
    logger.debug("Completed %s ops (%.2f MB) on node %s", ops, total_bytes / (1024**2), node_id)


class LocalClusterEmulator:
    """Emulates a distributed multi-node storage simulation cluster on local infrastructure."""

    def __init__(self, node_count: int = 4, cores_per_node: int = 2) -> None:
        self.node_count = node_count
        self.cores_per_node = cores_per_node
        self.total_cores = node_count * cores_per_node
        self.logger = get_logger("setve.cluster.emulator")

    async def run_emulated_cluster(
        self,
        duration_sec: float = 3.0,
        target_gbps: float = 8.0,
        block_size: int = 65536,
    ) -> ClusterTelemetrySummary:
        """Run synchronized multi-node cluster simulation using live gRPC barrier logic."""
        self.logger.info(
            "Initializing Local Cluster: %s nodes | %s total cores | Target: %.2f Gbps",
            self.node_count,
            self.total_cores,
            target_gbps,
        )

        nodes = [(f"node-{i:02d}", self.cores_per_node) for i in range(self.node_count)]
        target_bps = target_gbps * (1024**3)

        # 1. Distributed deterministic shard allocation
        shards = DeterministicShardGenerator.generate_cluster_shards(
            global_seed=12345,
            nodes=nodes,
            target_total_throughput_bps=target_bps,
            block_size=block_size,
        )

        # 2. Live barrier synchronization handshake
        sync_servicer = ClusterSyncServicer(expected_node_count=self.node_count)
        await asyncio.gather(
            *(
                sync_servicer.signal_ready(type("Req", (), {"node_id": node_name})())
                for node_name, _ in nodes
            )
        )

        # 3. Launch simulated node worker fleet
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_target = os.path.join(tmp_dir, "cluster_sim")
            result_queue: mp.Queue[WorkerTelemetryResult] = mp.Queue()
            processes: list[mp.Process] = []

            start_time = time.perf_counter()

            for node_name, _ in nodes:
                node_shards = shards.get(node_name, [])
                for core_idx, shard_spec in enumerate(node_shards):
                    p = mp.Process(
                        target=run_simulated_node_worker,
                        args=(
                            node_name,
                            core_idx,
                            shard_spec,
                            base_target,
                            duration_sec,
                            result_queue,
                        ),
                        daemon=True,
                    )
                    p.start()
                    processes.append(p)

            for p in processes:
                p.join()

            elapsed_sec = max(time.perf_counter() - start_time, 1e-6)

            # 4. Aggregate telemetry across all simulated nodes
            results: list[WorkerTelemetryResult] = []
            while not result_queue.empty():
                try:
                    results.append(result_queue.get_nowait())
                except Exception:
                    break

        total_ops = sum(r.total_ops for r in results)
        total_bytes = sum(r.total_bytes for r in results)
        agg_gbps = (total_bytes * 8) / (elapsed_sec * 1e9)
        p99_latencies = [r.p99_ms for r in results] if results else [0.0]

        summary = ClusterTelemetrySummary(
            run_id="local-cluster-sim-01",
            target_uri=f"posix://{tmp_dir}/cluster_sim",
            total_cores=len(processes),
            total_ops=total_ops,
            total_bytes=total_bytes,
            duration_sec=elapsed_sec,
            aggregate_throughput_gbps=agg_gbps,
            max_p99_ms=max(p99_latencies),
            avg_p99_ms=sum(p99_latencies) / len(p99_latencies),
            workers=results,
        )

        self.logger.info(
            "Cluster Run Finished: %s nodes | %s ops (%.2f MB) | %.2f Gbps | p99: %.3f ms",
            self.node_count,
            total_ops,
            total_bytes / (1024**2),
            agg_gbps,
            summary.max_p99_ms,
        )
        return summary


def main() -> None:
    """CLI entrypoint for local cluster emulation."""
    parser = argparse.ArgumentParser(description="SETVE Local Multi-Node Cluster Emulator")
    parser.add_argument("--nodes", type=int, default=4, help="Number of simulated cluster nodes")
    parser.add_argument("--cores-per-node", type=int, default=2, help="Cores per node")
    parser.add_argument("--duration", type=float, default=2.0, help="Test duration in seconds")
    parser.add_argument("--rate", type=float, default=5.0, help="Target aggregate rate in Gbps")
    args = parser.parse_args()

    configure_logging()
    emulator = LocalClusterEmulator(node_count=args.nodes, cores_per_node=args.cores_per_node)
    summary = asyncio.run(
        emulator.run_emulated_cluster(duration_sec=args.duration, target_gbps=args.rate)
    )

    total_c = args.nodes * args.cores_per_node
    print("\n" + "=" * 80)
    print(f"  SETVE LOCAL CLUSTER SIMULATION REPORT ({args.nodes} Nodes | {total_c} Cores)")
    print("=" * 80)
    print(f"[*] Total Ops:        {summary.total_ops:,} ops")
    print(f"[*] Transferred:      {summary.total_bytes / (1024**2):.2f} MB")
    print(f"[*] Aggregate Rate:   {summary.aggregate_throughput_gbps:.2f} Gbps")
    print(f"[*] Max p99 Latency:  {summary.max_p99_ms:.3f} ms (Avg: {summary.avg_p99_ms:.3f} ms)")
    print("=" * 80)


if __name__ == "__main__":
    main()
