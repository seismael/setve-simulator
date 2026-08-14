"""Tests for MultiCoreOrchestrator telemetry aggregation and eBPF triangulation."""

import tempfile
from pathlib import Path

from setve.orchestrator.master import MultiCoreOrchestrator
from setve.payload.blueprint import WorkloadBlueprint


def test_master_orchestrator_telemetry_aggregation() -> None:
    """Verify MultiCoreOrchestrator runs workers, aggregates metrics, and returns summary."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_path = Path(tmp_dir) / "master_test"
        blueprint = WorkloadBlueprint.from_dict(
            {
                "run_id": "master-telemetry-test",
                "target_uri": f"file://{test_path}",
                "block_size_bytes": 4096,
                "entropy_ratio": 0.5,
                "target_throughput_gbps": 1,
                "duration_seconds": 1,
                "global_seed": 42,
            }
        )

        orchestrator = MultiCoreOrchestrator(core_ids=[0])
        summary = orchestrator.start(blueprint)

        assert summary.run_id == "master-telemetry-test"
        assert summary.total_cores == 1
        assert summary.total_ops > 0
        assert summary.total_bytes > 0
        assert summary.duration_sec > 0.0
        assert summary.aggregate_throughput_gbps > 0.0
        assert len(summary.workers) == 1

        worker = summary.workers[0]
        assert worker.core_id == 0
        assert worker.total_ops == summary.total_ops
        assert worker.total_bytes == summary.total_bytes

        # Verify ASCII report table generation
        table = summary.format_table()
        assert "SETVE SIMULATION & TELEMETRY REPORT" in table
        assert "master-telemetry-test" in table

        # Verify Prometheus metric export
        prom = summary.to_prometheus_metrics()
        assert "setve_cluster_ops_total" in prom
        assert "setve_cluster_throughput_gbps" in prom
