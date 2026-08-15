"""Comprehensive Local Deployment and Configuration Validation Script."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from setve.logging import configure_logging, get_logger


def validate_docker_configs() -> bool:
    """Validate Dockerfile, compose, and provisioning file integrity."""
    logger = get_logger("setve.deploy.validate")
    base_dir = Path(__file__).parent.parent
    docker_dir = base_dir / "deployments" / "docker"

    required_files = [
        docker_dir / "Dockerfile",
        docker_dir / "docker-compose.yml",
        docker_dir / "prometheus.yml",
        docker_dir / "entrypoint.sh",
        docker_dir / "grafana" / "provisioning" / "datasources" / "datasource.yml",
        docker_dir / "grafana" / "provisioning" / "dashboards" / "dashboard.yml",
        docker_dir / "grafana" / "dashboards" / "setve_telemetry.json",
    ]

    all_valid = True
    for f in required_files:
        if not f.exists():
            logger.error("Missing required deployment configuration file: %s", f)
            all_valid = False
        else:
            logger.info("Found deployment artifact: %s (%d bytes)", f.name, f.stat().st_size)

    # Validate JSON syntax for Grafana dashboard
    dashboard_json = docker_dir / "grafana" / "dashboards" / "setve_telemetry.json"
    if dashboard_json.exists():
        try:
            with open(dashboard_json, encoding="utf-8") as fh:
                parsed = json.load(fh)
                panels = len(parsed.get("panels", []))
                logger.info("Grafana dashboard JSON is valid with %d panels", panels)
        except Exception as e:
            logger.error("Invalid Grafana JSON syntax: %s", e)
            all_valid = False

    return all_valid


async def validate_local_cluster_runner() -> bool:
    """Validate that local cluster emulator runs successfully end to end."""
    logger = get_logger("setve.deploy.validate")
    from deployments.local_cluster.cluster_runner import LocalClusterEmulator

    try:
        emulator = LocalClusterEmulator(node_count=2, cores_per_node=1)
        summary = await emulator.run_emulated_cluster(duration_sec=1.0, target_gbps=2.0)
        logger.info(
            "Local Cluster Validation Passed: %d ops, %.2f Gbps, p99=%.3f ms",
            summary.total_ops,
            summary.aggregate_throughput_gbps,
            summary.max_p99_ms,
        )
        return summary.total_ops > 0
    except Exception as e:
        logger.exception("Local cluster emulator validation failed: %s", e)
        return False


async def main() -> int:
    """Run all local deployment validations."""
    configure_logging()
    logger = get_logger("setve.deploy.validate")

    print("\n" + "=" * 80)
    print("  SETVE LOCAL DEPLOYMENT & TESTING CAPABILITY VALIDATOR")
    print("=" * 80)

    docker_ok = validate_docker_configs()
    cluster_ok = await validate_local_cluster_runner()

    print("\n" + "-" * 80)
    print(f"[*] Docker & Compose Configuration Integrity: {'PASS' if docker_ok else 'FAIL'}")
    print(f"[*] Local Multi-Node Cluster Emulation:       {'PASS' if cluster_ok else 'FAIL'}")
    print("-" * 80)

    if docker_ok and cluster_ok:
        logger.info("All local deployment capabilities successfully validated!")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
