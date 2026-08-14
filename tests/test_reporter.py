"""Tests for TelemetryReporter, Prometheus metric generation, and table formatting."""

from setve.validation.evaluator import DivergenceResult
from setve.validation.reporter import ClusterTelemetrySummary, WorkerTelemetryResult


def test_cluster_telemetry_summary_to_dict_and_json() -> None:
    """Verify ClusterTelemetrySummary serializes cleanly to dict and valid JSON."""
    worker1 = WorkerTelemetryResult(
        core_id=0,
        node_id="node-1",
        total_ops=100,
        total_bytes=104857600,
        duration_sec=1.0,
        p50_ms=0.5,
        p90_ms=1.0,
        p99_ms=2.0,
        p999_ms=3.0,
        throughput_gbps=0.8388,
    )
    divergence = DivergenceResult(
        client_bytes=104857600,
        probe_bytes=104857600,
        delta_bytes=0,
        divergence_percent=0.0,
        is_valid=True,
    )
    summary = ClusterTelemetrySummary(
        run_id="test-run-100",
        target_uri="file://test",
        total_cores=1,
        total_ops=100,
        total_bytes=104857600,
        duration_sec=1.0,
        aggregate_throughput_gbps=0.8388,
        max_p99_ms=2.0,
        avg_p99_ms=2.0,
        workers=[worker1],
        divergence=divergence,
    )

    data = summary.to_dict()
    assert data["run_id"] == "test-run-100"
    assert data["total_ops"] == 100
    assert len(data["workers"]) == 1

    json_str = summary.to_json()
    assert "test-run-100" in json_str
    assert "workers" in json_str


def test_cluster_telemetry_prometheus_export() -> None:
    """Verify Prometheus text exposition export produces valid format lines."""
    summary = ClusterTelemetrySummary(
        run_id="prom-run-1",
        target_uri="posix://storage",
        total_cores=2,
        total_ops=5000,
        total_bytes=5242880000,
        duration_sec=2.0,
        aggregate_throughput_gbps=20.97,
        max_p99_ms=0.85,
        avg_p99_ms=0.75,
        workers=[],
        divergence=DivergenceResult(
            client_bytes=5242880000,
            probe_bytes=5242880000,
            delta_bytes=0,
            divergence_percent=0.0,
            is_valid=True,
        ),
    )

    prom_text = summary.to_prometheus_metrics()
    assert 'setve_cluster_ops_total{run_id="prom-run-1"} 5000' in prom_text
    assert 'setve_cluster_bytes_total{run_id="prom-run-1"} 5242880000' in prom_text
    assert 'setve_cluster_throughput_gbps{run_id="prom-run-1"} 20.9700' in prom_text
    assert 'setve_telemetry_is_valid{run_id="prom-run-1"} 1' in prom_text


def test_cluster_telemetry_table_formatting() -> None:
    """Verify ASCII table formatting includes all summary rows and core breakdowns."""
    worker = WorkerTelemetryResult(
        core_id=3,
        node_id="node-a",
        total_ops=50,
        total_bytes=52428800,
        duration_sec=0.5,
        p50_ms=0.2,
        p90_ms=0.4,
        p99_ms=0.8,
        p999_ms=1.2,
        throughput_gbps=0.838,
    )
    summary = ClusterTelemetrySummary(
        run_id="table-run",
        target_uri="file://local",
        total_cores=1,
        total_ops=50,
        total_bytes=52428800,
        duration_sec=0.5,
        aggregate_throughput_gbps=0.838,
        max_p99_ms=0.8,
        avg_p99_ms=0.8,
        workers=[worker],
    )

    table = summary.format_table()
    assert "SETVE SIMULATION & TELEMETRY REPORT: table-run" in table
    assert "CORE BREAKDOWN" in table
    assert "3 |" in table
