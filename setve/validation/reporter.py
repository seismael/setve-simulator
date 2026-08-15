"""Telemetry Formatting, Structured Logging, and Prometheus / ClickHouse Exporters."""

import json
import logging
from dataclasses import asdict, dataclass
from typing import Any

from setve.validation.evaluator import DivergenceResult

logger = logging.getLogger("setve.telemetry")


@dataclass(frozen=True, slots=True)
class WorkerTelemetryResult:
    """Telemetry metrics collected from a single core-pinned worker process."""

    core_id: int
    node_id: str
    total_ops: int
    total_bytes: int
    duration_sec: float
    p50_ms: float
    p90_ms: float
    p99_ms: float
    p999_ms: float
    throughput_gbps: float
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class ClusterTelemetrySummary:
    """Aggregated telemetry metrics across the entire simulation cluster."""

    run_id: str
    target_uri: str
    total_cores: int
    total_ops: int
    total_bytes: int
    duration_sec: float
    aggregate_throughput_gbps: float
    max_p99_ms: float
    avg_p99_ms: float
    workers: list[WorkerTelemetryResult]
    divergence: DivergenceResult | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize cluster telemetry summary to JSON-compatible dictionary."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Serialize cluster telemetry summary to formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def to_prometheus_metrics(self) -> str:
        """Export metrics in Prometheus text exposition format."""
        lines = [
            "# HELP setve_cluster_ops_total Total I/O operations completed by SETVE cluster",
            "# TYPE setve_cluster_ops_total counter",
            f'setve_cluster_ops_total{{run_id="{self.run_id}"}} {self.total_ops}',
            "# HELP setve_cluster_bytes_total Total bytes transferred by SETVE cluster",
            "# TYPE setve_cluster_bytes_total counter",
            f'setve_cluster_bytes_total{{run_id="{self.run_id}"}} {self.total_bytes}',
            "# HELP setve_cluster_throughput_gbps Aggregate cluster throughput in Gbps",
            "# TYPE setve_cluster_throughput_gbps gauge",
            f'setve_cluster_throughput_gbps{{run_id="{self.run_id}"}} '
            f"{self.aggregate_throughput_gbps:.4f}",
            "# HELP setve_cluster_latency_p99_ms Maximum p99 latency observed across workers",
            "# TYPE setve_cluster_latency_p99_ms gauge",
            f'setve_cluster_latency_p99_ms{{run_id="{self.run_id}"}} {self.max_p99_ms:.4f}',
        ]
        if self.divergence is not None:
            valid_int = 1 if self.divergence.is_valid else 0
            lines.extend(
                [
                    "# HELP setve_telemetry_divergence_percent Telemetry skew vs physical probe",
                    "# TYPE setve_telemetry_divergence_percent gauge",
                    f'setve_telemetry_divergence_percent{{run_id="{self.run_id}"}} '
                    f"{self.divergence.divergence_percent:.4f}",
                    "# HELP setve_telemetry_is_valid Boolean flag indicating telemetry validity",
                    "# TYPE setve_telemetry_is_valid gauge",
                    f'setve_telemetry_is_valid{{run_id="{self.run_id}"}} {valid_int}',
                ]
            )
        return "\n".join(lines) + "\n"

    def format_table(self) -> str:
        """Format an ASCII-safe human-readable telemetry summary table."""
        border = "=" * 80
        divider = "-" * 80
        gb_data = self.total_bytes / (1024**3)
        mb_data = self.total_bytes / (1024**2)
        gb_rate = self.aggregate_throughput_gbps / 8
        rate_str = f"{self.aggregate_throughput_gbps:.2f} Gbps ({gb_rate:.2f} GB/s)"

        lines = [
            f"+{border}+",
            f"| SETVE SIMULATION & TELEMETRY REPORT: {self.run_id:<42} |",
            f"+{border}+",
            f"| Target URI:     {self.target_uri:<62} |",
            f"| Total Cores:    {self.total_cores:<62} |",
            f"| Duration:       {self.duration_sec:.2f} s{'':<56} |",
            f"| Total Ops:      {self.total_ops:<62} |",
            f"| Total Data:     {gb_data:.2f} GB ({mb_data:.1f} MB){'':<45} |",
            f"| Aggregate Rate: {rate_str:<62} |",
            f"| Max p99 Lat:    {self.max_p99_ms:.3f} ms (Avg: {self.avg_p99_ms:.3f} ms){'':<42} |",
        ]

        if self.divergence is not None:
            status_str = "VALID (<= 0.1%)" if self.divergence.is_valid else "ALARM (> 0.1%)"
            skew_str = (
                f"{self.divergence.divergence_percent:.4f}% "
                f"({self.divergence.delta_bytes} bytes delta)"
            )
            lines.extend(
                [
                    f"+{divider}+",
                    f"| OUT-OF-BAND TELEMETRY TRIANGULATION: {status_str:<40} |",
                    f"| Client Data:    {self.divergence.client_bytes:<62} |",
                    f"| Probe Data:     {self.divergence.probe_bytes:<62} |",
                    f"| Metric Skew:    {skew_str:<62} |",
                ]
            )

        if self.workers:
            lines.extend(
                [
                    f"+{divider}+",
                    f"| CORE BREAKDOWN:{'':<63} |",
                    "|  Core |  Operations  |   Bytes Transferred   | Rate (Gbps) | p99 Latency |",
                    f"+{divider}+",
                ]
            )
            for w in self.workers:
                w_mb = w.total_bytes / (1024**2)
                lines.append(
                    f"|  {w.core_id:>4} | {w.total_ops:>12} | {w_mb:>17.2f} MB "
                    f"| {w.throughput_gbps:>11.2f} | {w.p99_ms:>9.3f} ms |"
                )

        lines.append(f"+{border}+")
        return "\n".join(lines)
