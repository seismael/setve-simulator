"""Automated Test Suite for Local Deployment & Cluster Emulation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from deployments.local_cluster.cluster_runner import LocalClusterEmulator


def test_docker_and_compose_configs_exist() -> None:
    """Verify all Docker, Prometheus, and Grafana deployment artifacts are valid and present."""
    base_dir = Path(__file__).parent.parent
    docker_dir = base_dir / "deployments" / "docker"

    dockerfile = docker_dir / "Dockerfile"
    compose = docker_dir / "docker-compose.yml"
    prom_cfg = docker_dir / "prometheus.yml"
    entrypoint = docker_dir / "entrypoint.sh"
    grafana_dash = docker_dir / "grafana" / "dashboards" / "setve_telemetry.json"

    assert dockerfile.exists()
    assert compose.exists()
    assert prom_cfg.exists()
    assert entrypoint.exists()
    assert grafana_dash.exists()

    # Verify Grafana JSON schema
    with open(grafana_dash, encoding="utf-8") as f:
        dash_data = json.load(f)
        assert "panels" in dash_data
        assert len(dash_data["panels"]) >= 3


@pytest.mark.asyncio
async def test_local_cluster_emulator_execution() -> None:
    """Verify LocalClusterEmulator runs multi-node simulation with barrier sync on local host."""
    emulator = LocalClusterEmulator(node_count=2, cores_per_node=2)
    summary = await emulator.run_emulated_cluster(duration_sec=1.0, target_gbps=2.0)

    assert summary.total_cores == 4
    assert summary.total_ops > 0
    assert summary.total_bytes > 0
    assert summary.aggregate_throughput_gbps > 0.0
    assert len(summary.workers) == 4
    assert summary.max_p99_ms >= 0.0
