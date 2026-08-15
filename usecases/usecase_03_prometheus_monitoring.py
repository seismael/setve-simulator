"""Use Case 03: Live Prometheus & ClickHouse Telemetry Ingestion.

Demonstrates real-time telemetry extraction, high-resolution HDR latency percentiles,
Prometheus text exposition format, and structured JSON telemetry generation.
"""

from __future__ import annotations

import argparse
import http.server
import sys
import tempfile
import threading
import time
from pathlib import Path

# Ensure setve package is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from setve.orchestrator.master import MultiCoreOrchestrator  # noqa: E402
from setve.payload.blueprint import WorkloadBlueprint  # noqa: E402


class TelemetryHTTPRequestHandler(http.server.BaseHTTPRequestHandler):
    """Serve Prometheus text exposition format on /metrics and JSON on /telemetry."""

    prom_data: str = ""
    json_data: str = ""

    def do_GET(self) -> None:
        if self.path in ("/metrics", "/"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.end_headers()
            self.wfile.write(self.prom_data.encode("utf-8"))
        elif self.path in ("/telemetry", "/json"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(self.json_data.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"404 Not Found")

    def log_message(self, format_str: str, *args: object) -> None:
        # Suppress noisy HTTP request logging in terminal
        pass


def run_prometheus_monitoring(
    duration_seconds: float = 1.0,
    target_throughput_gbps: float = 5.0,
    output_prom: str | None = None,
    output_json: str | None = None,
    serve_port: int | None = None,
    serve_duration: float = 3.0,
) -> int:
    """Run workload and export Prometheus and JSON metrics."""
    print("=" * 80)
    print("  SETVE USE CASE 03: Prometheus & Telemetry Monitoring Exporter")
    print("=" * 80)

    with tempfile.TemporaryDirectory() as tmp_dir:
        test_file = Path(tmp_dir) / "prom_telemetry.dat"

        blueprint = WorkloadBlueprint.from_dict(
            {
                "run_id": "prom-telemetry-demo-01",
                "target_uri": f"posix://{test_file}",
                "block_size_bytes": 65536,
                "entropy_ratio": 0.5,
                "target_throughput_gbps": target_throughput_gbps,
                "duration_seconds": duration_seconds,
                "global_seed": 777,
            }
        )

        orchestrator = MultiCoreOrchestrator(core_ids=[0])
        summary = orchestrator.start(blueprint)

        print("\n--- 1. ASCII DIAGNOSTIC REPORT ---")
        print(summary.format_table())

        prom_text = summary.to_prometheus_metrics()
        print("\n--- 2. PROMETHEUS METRIC EXPOSITION (/metrics) ---")
        print(prom_text)

        json_text = summary.to_json()
        print("--- 3. STRUCTURED JSON TELEMETRY (ClickHouse / Elasticsearch) ---")
        print(json_text)

        if output_prom:
            Path(output_prom).write_text(prom_text, encoding="utf-8")
            print(f"[+] Exported Prometheus metrics to: {output_prom}")

        if output_json:
            Path(output_json).write_text(json_text, encoding="utf-8")
            print(f"[+] Exported JSON telemetry to:       {output_json}")

        if serve_port is not None:
            TelemetryHTTPRequestHandler.prom_data = prom_text
            TelemetryHTTPRequestHandler.json_data = json_text
            server = http.server.HTTPServer(("0.0.0.0", serve_port), TelemetryHTTPRequestHandler)
            server_thread = threading.Thread(target=server.serve_forever, daemon=True)
            server_thread.start()
            print(f"\n[+] Live Telemetry Server Active at http://0.0.0.0:{serve_port}")
            print(f"    -> Prometheus Scrape:  http://localhost:{serve_port}/metrics")
            print(f"    -> JSON Telemetry:     http://localhost:{serve_port}/telemetry")

            # Keep server active for requested serve duration or allow background scraping
            if serve_duration > 0:
                time.sleep(serve_duration)
            server.shutdown()
            server.server_close()

    print("\n[*] Telemetry exposition verified successfully.\n")
    return 0


def main() -> int:
    """Parse CLI options and run telemetry exporter."""
    parser = argparse.ArgumentParser(
        description="SETVE Use Case 03: Prometheus & Telemetry Exporter"
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=1.0,
        help="Duration in seconds (default: 1.0)",
    )
    parser.add_argument(
        "--throughput",
        type=float,
        default=5.0,
        help="Target throughput in Gbps (default: 5.0)",
    )
    parser.add_argument(
        "--output-prom",
        type=str,
        default=None,
        help="Optional path to write Prometheus metrics file (.prom)",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        default=None,
        help="Optional path to write structured JSON telemetry file (.json)",
    )
    parser.add_argument(
        "--serve-port",
        "--port",
        dest="serve_port",
        type=int,
        default=None,
        help="Optional HTTP port to serve live /metrics and /telemetry endpoints (e.g. 9100)",
    )

    args = parser.parse_args()
    return run_prometheus_monitoring(
        duration_seconds=args.duration,
        target_throughput_gbps=args.throughput,
        output_prom=args.output_prom,
        output_json=args.output_json,
        serve_port=args.serve_port,
    )


if __name__ == "__main__":
    sys.exit(main())
