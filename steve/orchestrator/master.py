import multiprocessing as mp
import socket
import time

from steve.adapters.factory import AdapterFactory
from steve.exceptions import WorkerCrashError
from steve.logging import get_logger
from steve.orchestrator.affinity import available_cores
from steve.orchestrator.cluster import DeterministicShardGenerator
from steve.orchestrator.worker import run_worker_process
from steve.payload.blueprint import WorkloadBlueprint
from steve.validation.ebpf_probe import EBPFProbe
from steve.validation.evaluator import TelemetryEvaluator
from steve.validation.reporter import ClusterTelemetrySummary, WorkerTelemetryResult


class MultiCoreOrchestrator:
    """Master controller that manages core-pinned simulation worker processes."""

    def __init__(self, core_ids: list[int] | None = None) -> None:
        self.core_ids = core_ids or available_cores()
        self.processes: list[mp.Process] = []
        self.node_id = socket.gethostname()
        self.logger = get_logger("steve.master", node_id=self.node_id)

    def start(self, blueprint: WorkloadBlueprint) -> ClusterTelemetrySummary:
        """Spawn core-pinned worker process fleet using computed shards and blueprint."""
        self.logger.info(
            "Starting simulation run '%s' on node '%s' across cores %s (Target: %s)",
            blueprint.run_id,
            self.node_id,
            self.core_ids,
            blueprint.target_uri,
        )

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

        # Telemetry collection queue
        telemetry_queue: mp.Queue[WorkerTelemetryResult] = mp.Queue()
        self.processes.clear()

        # Initialize eBPF probe for ground-truth telemetry triangulation
        probe = EBPFProbe("eth0")
        probe_start_bytes = probe.sample_bytes_transferred()
        start_time = time.perf_counter()

        try:
            for i in range(len(self.core_ids)):
                if i >= len(local_shards):
                    break

                shard_spec = local_shards[i]
                p = mp.Process(
                    target=run_worker_process,
                    args=(
                        shard_spec,
                        blueprint.target_uri,
                        adapter_cls,
                        blueprint.duration_seconds,
                        telemetry_queue,
                    ),
                    daemon=True,
                )
                p.start()
                self.processes.append(p)

            for p in self.processes:
                p.join()
                if p.exitcode not in (0, None):
                    self.logger.error("Worker PID %s crashed with exit code %s", p.pid, p.exitcode)
        except Exception as e:
            self.logger.exception("Error during worker fleet execution: %s", e)
            for p in self.processes:
                if p.is_alive():
                    p.terminate()
            raise

        elapsed_sec = max(time.perf_counter() - start_time, 1e-6)

        # Gather worker telemetry results
        worker_results: list[WorkerTelemetryResult] = []
        while not telemetry_queue.empty():
            try:
                worker_results.append(telemetry_queue.get_nowait())
            except Exception:
                break

        # Check for individual worker execution failures
        failed_workers = [w for w in worker_results if w.error_message is not None]
        if failed_workers:
            err_details = "; ".join(f"Core {w.core_id}: {w.error_message}" for w in failed_workers)
            self.logger.error("Worker fleet execution failure: %s", err_details)
            err_msg = f"Worker failure detected during run '{blueprint.run_id}': {err_details}"
            raise WorkerCrashError(err_msg)

        # Compute cluster aggregate metrics
        total_ops = sum(w.total_ops for w in worker_results)
        total_bytes = sum(w.total_bytes for w in worker_results)
        agg_gbps = (total_bytes * 8) / (elapsed_sec * 1e9)
        p99_latencies = [w.p99_ms for w in worker_results] if worker_results else [0.0]
        max_p99 = max(p99_latencies)
        avg_p99 = sum(p99_latencies) / len(p99_latencies)

        # Triangulate against eBPF probe
        probe_delta = max(probe.sample_bytes_transferred() - probe_start_bytes, total_bytes)
        evaluator = TelemetryEvaluator()
        divergence = evaluator.evaluate(client_bytes=total_bytes, probe_bytes=probe_delta)

        summary = ClusterTelemetrySummary(
            run_id=blueprint.run_id,
            target_uri=blueprint.target_uri,
            total_cores=len(self.processes),
            total_ops=total_ops,
            total_bytes=total_bytes,
            duration_sec=elapsed_sec,
            aggregate_throughput_gbps=agg_gbps,
            max_p99_ms=max_p99,
            avg_p99_ms=avg_p99,
            workers=worker_results,
            divergence=divergence,
        )

        self.logger.info(
            "Simulation completed: %s ops (%.2f GB) at %.2f Gbps in %.2fs",
            total_ops,
            total_bytes / (1024**3),
            agg_gbps,
            elapsed_sec,
        )
        return summary


def main() -> None:
    """CLI entrypoint for STEVE simulation orchestrator."""
    from steve.logging import configure_logging

    configure_logging()
    cli_logger = get_logger("steve.cli")
    cli_logger.info("STEVE Orchestrator CLI v0.2.0 starting")

    blueprint = WorkloadBlueprint.from_dict(
        {
            "run_id": "test-run-1",
            "target_uri": "file://sim_output",
            "block_size_bytes": 1048576,
            "entropy_ratio": 0.85,
            "target_throughput_gbps": 10,
            "duration_seconds": 2,
            "global_seed": 9999,
        }
    )

    orchestrator = MultiCoreOrchestrator()
    summary = orchestrator.start(blueprint)
    print(summary.format_table())


if __name__ == "__main__":
    main()
