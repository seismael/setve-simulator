"""Automated Test Suite for Canonical 3-Tier Deployment Architecture."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from deploy.emulator.cluster_runner import LocalClusterEmulator


def test_packaging_artifacts_exist() -> None:
    """Verify Docker, Helm, and Operator packaging artifacts."""
    base_dir = Path(__file__).parent.parent
    pkg_dir = base_dir / "deploy" / "packaging"

    # Docker
    docker_dir = pkg_dir / "docker"
    assert (docker_dir / "Dockerfile").exists()
    assert (docker_dir / "entrypoint.sh").exists()
    assert (docker_dir / "README.md").exists()

    # Helm
    helm_dir = pkg_dir / "helm" / "steve-cluster"
    assert (helm_dir / "Chart.yaml").exists()
    assert (helm_dir / "values.yaml").exists()
    assert (helm_dir / "templates" / "master-deployment.yaml").exists()
    assert (helm_dir / "templates" / "worker-daemonset.yaml").exists()
    assert (helm_dir / "templates" / "service.yaml").exists()

    # Operator & CRD
    op_dir = pkg_dir / "operator"
    assert (op_dir / "controller.py").exists()
    assert (op_dir / "crds" / "stevecluster-crd.yaml").exists()


def test_environments_overlays_exist() -> None:
    """Verify tiered environment configurations (local, dev, staging, prod)."""
    base_dir = Path(__file__).parent.parent
    env_dir = base_dir / "deploy" / "environments"

    # Local Compose Stack & Grafana Dashboards
    local_dir = env_dir / "local"
    assert (local_dir / "docker-compose.yml").exists()
    assert (local_dir / "prometheus.yml").exists()
    assert (local_dir / "grafana" / "dashboards" / "steve_telemetry.json").exists()

    # Validate Grafana JSON schema
    grafana_dash = local_dir / "grafana" / "dashboards" / "steve_telemetry.json"
    with open(grafana_dash, encoding="utf-8") as f:
        dash_data = json.load(f)
        assert "panels" in dash_data
        assert len(dash_data["panels"]) >= 3

    # Dev, Staging, Prod
    assert (env_dir / "dev" / "terraform" / "main.tf").exists()
    assert (env_dir / "staging" / "values.staging.yaml").exists()
    assert (env_dir / "prod" / "values.prod.yaml").exists()


@pytest.mark.asyncio
async def test_cluster_emulator_execution() -> None:
    """Verify LocalClusterEmulator runs multi-node simulation with barrier sync on local host."""
    emulator = LocalClusterEmulator(node_count=2, cores_per_node=2)
    summary = await emulator.run_emulated_cluster(duration_sec=1.0, target_gbps=2.0)

    assert summary.total_cores == 4
    assert summary.total_ops > 0
    assert summary.total_bytes > 0
    assert summary.aggregate_throughput_gbps > 0.0
    assert len(summary.workers) == 4
    assert summary.max_p99_ms >= 0.0
