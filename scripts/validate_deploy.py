"""Comprehensive Deployment & Infrastructure Architecture Validation Script."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from setve.logging import configure_logging, get_logger


def validate_packaging_artifacts() -> bool:
    """Validate Docker, Helm, and Operator packaging artifacts."""
    logger = get_logger("setve.deploy.validate")
    base_dir = Path(__file__).parent.parent
    pkg_dir = base_dir / "deploy" / "packaging"

    required_files = [
        pkg_dir / "docker" / "Dockerfile",
        pkg_dir / "docker" / "entrypoint.sh",
        pkg_dir / "docker" / "README.md",
        pkg_dir / "helm" / "setve-cluster" / "Chart.yaml",
        pkg_dir / "helm" / "setve-cluster" / "values.yaml",
        pkg_dir / "helm" / "setve-cluster" / "templates" / "master-deployment.yaml",
        pkg_dir / "helm" / "setve-cluster" / "templates" / "worker-daemonset.yaml",
        pkg_dir / "helm" / "setve-cluster" / "templates" / "service.yaml",
        pkg_dir / "operator" / "controller.py",
        pkg_dir / "operator" / "crds" / "setvecluster-crd.yaml",
    ]

    all_valid = True
    for f in required_files:
        if not f.exists():
            logger.error("Missing packaging artifact: %s", f)
            all_valid = False
        else:
            logger.info("Found packaging artifact: %s (%d bytes)", f.name, f.stat().st_size)

    return all_valid


def validate_environment_overlays() -> bool:
    """Validate environment progression overlays (local, dev, staging, prod)."""
    logger = get_logger("setve.deploy.validate")
    base_dir = Path(__file__).parent.parent
    env_dir = base_dir / "deploy" / "environments"

    required_files = [
        env_dir / "local" / "docker-compose.yml",
        env_dir / "local" / "prometheus.yml",
        env_dir / "local" / "grafana" / "provisioning" / "datasources" / "datasource.yml",
        env_dir / "local" / "grafana" / "provisioning" / "dashboards" / "dashboard.yml",
        env_dir / "local" / "grafana" / "dashboards" / "setve_telemetry.json",
        env_dir / "dev" / "terraform" / "main.tf",
        env_dir / "staging" / "values.staging.yaml",
        env_dir / "prod" / "values.prod.yaml",
    ]

    all_valid = True
    for f in required_files:
        if not f.exists():
            logger.error("Missing environment file: %s", f)
            all_valid = False
        else:
            logger.info("Found environment manifest: %s (%d bytes)", f.name, f.stat().st_size)

    # Validate JSON syntax for Grafana dashboard
    dashboard_json = env_dir / "local" / "grafana" / "dashboards" / "setve_telemetry.json"
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


async def validate_cluster_emulator() -> bool:
    """Validate that local cluster emulator runs successfully end to end."""
    logger = get_logger("setve.deploy.validate")
    from deploy.emulator.cluster_runner import LocalClusterEmulator

    try:
        emulator = LocalClusterEmulator(node_count=2, cores_per_node=1)
        summary = await emulator.run_emulated_cluster(duration_sec=1.0, target_gbps=2.0)
        logger.info(
            "Cluster Emulator Validation Passed: %d ops, %.2f Gbps, p99=%.3f ms",
            summary.total_ops,
            summary.aggregate_throughput_gbps,
            summary.max_p99_ms,
        )
        return summary.total_ops > 0
    except Exception as e:
        logger.exception("Cluster emulator validation failed: %s", e)
        return False


async def main() -> int:
    """Run all deployment architecture validation checks."""
    configure_logging()
    logger = get_logger("setve.deploy.validate")

    print("\n" + "=" * 80)
    print("  SETVE 3-TIER ENTERPRISE DEPLOYMENT ARCHITECTURE VALIDATOR")
    print("=" * 80)

    pkg_ok = validate_packaging_artifacts()
    env_ok = validate_environment_overlays()
    emu_ok = await validate_cluster_emulator()

    print("-" * 80)
    print(f"[*] 1. Packaging Specs (Docker, Helm, Operator):   {'PASS' if pkg_ok else 'FAIL'}")
    print(f"[*] 2. Environment Overlays (local, dev, stg, prd): {'PASS' if env_ok else 'FAIL'}")
    print(f"[*] 3. Local Cluster Emulator & Barrier Sync:      {'PASS' if emu_ok else 'FAIL'}")
    print("-" * 80)

    if pkg_ok and env_ok and emu_ok:
        logger.info("All 3-tier enterprise deployment capabilities successfully validated!")
        return 0
    else:
        logger.error("Deployment validation failed.")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
