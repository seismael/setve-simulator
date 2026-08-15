"""Verification test suite for all production use case scripts."""

from __future__ import annotations

from pathlib import Path

import pytest

from usecases.usecase_01_storage_stress import run_storage_stress
from usecases.usecase_02_dedup_compression import run_dedup_compression_bench
from usecases.usecase_03_prometheus_monitoring import run_prometheus_monitoring
from usecases.usecase_04_ebpf_triangulation import run_ebpf_triangulation
from usecases.usecase_05_ai_vector_s3 import run_ai_vector_s3_simulation
from usecases.usecase_06_ai_kv_cache_checkpointing import run_ai_kv_cache_simulation
from usecases.usecase_07_multitenant_qos_noisy_neighbor import run_multitenant_qos_simulation
from usecases.usecase_08_chaos_node_failure import run_chaos_simulation
from usecases.usecase_09_storage_tiering_lifecycle import run_storage_tiering_simulation
from usecases.usecase_10_tail_latency_microburst import run_microburst_simulation


def test_usecase_01_storage_stress() -> None:
    """Verify Use Case 01 executes successfully with direct I/O and page-cache modes."""
    status_direct = run_storage_stress(
        target_path=None,
        block_size_bytes=4096,
        target_throughput_gbps=1.0,
        duration_seconds=0.3,
        entropy_ratio=0.5,
        num_cores=1,
        direct_io=True,
    )
    assert status_direct == 0

    status_buffered = run_storage_stress(
        target_path=None,
        block_size_bytes=4096,
        target_throughput_gbps=1.0,
        duration_seconds=0.3,
        entropy_ratio=0.0,
        num_cores=1,
        direct_io=False,
    )
    assert status_buffered == 0


def test_usecase_02_dedup_compression() -> None:
    """Verify Use Case 02 executes across entropy sweeps and dedup audit."""
    status = run_dedup_compression_bench(
        buffer_size_mb=1,
        iterations=10,
        verify_dedup=True,
    )
    assert status == 0


def test_usecase_03_prometheus_monitoring() -> None:
    """Verify Use Case 03 generates valid Prometheus and JSON metrics."""
    status = run_prometheus_monitoring(
        duration_seconds=0.3,
        target_throughput_gbps=1.0,
    )
    assert status == 0


def test_usecase_03_prometheus_file_exports() -> None:
    """Verify Use Case 03 exports .prom and .json files to disk."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp_dir:
        prom_out = str(Path(tmp_dir) / "test_metrics.prom")
        json_out = str(Path(tmp_dir) / "test_telemetry.json")
        status = run_prometheus_monitoring(
            duration_seconds=0.2,
            target_throughput_gbps=1.0,
            output_prom=prom_out,
            output_json=json_out,
        )
        assert status == 0
        assert Path(prom_out).exists()
        assert Path(json_out).exists()


def test_usecase_03_prometheus_server() -> None:
    """Verify Use Case 03 live HTTP server endpoint."""
    status = run_prometheus_monitoring(
        duration_seconds=0.2,
        target_throughput_gbps=1.0,
        serve_port=19100,
    )
    assert status == 0


def test_usecase_04_ebpf_triangulation_pass() -> None:
    """Verify Use Case 04 passes when metric drift is zero."""
    status = run_ebpf_triangulation(
        simulated_transfer_mb=100,
        skew_drift_bytes=0,
        tolerance_percent=0.1,
        mtu_bytes=1500,
    )
    assert status == 0


def test_usecase_04_ebpf_triangulation_fail() -> None:
    """Verify Use Case 04 returns non-zero exit status on excessive metric drift."""
    status = run_ebpf_triangulation(
        simulated_transfer_mb=100,
        skew_drift_bytes=10_000_000,  # 10 MB drift on 100 MB -> 10% skew > 0.1% tolerance
        tolerance_percent=0.1,
        mtu_bytes=9000,
    )
    assert status == 1


@pytest.mark.asyncio
async def test_usecase_05_ai_vector_s3() -> None:
    """Verify Use Case 05 executes vector concurrent search and S3 ingestion passes."""
    status = await run_ai_vector_s3_simulation(
        vector_ops=50,
        vector_queries=20,
        s3_chunks=5,
        dimension=1536,
        top_k=10,
        query_concurrency=4,
    )
    assert status == 0


@pytest.mark.asyncio
async def test_usecase_06_ai_kv_cache_checkpointing() -> None:
    """Verify Use Case 06 AI KV-cache prefill, PagedAttention decode, and checkpointing."""
    status = await run_ai_kv_cache_simulation(
        prefill_mb=4,
        decode_tokens=50,
        checkpoint_mb=4,
        target_uri=None,
        page_block_kb=16,
    )
    assert status == 0


@pytest.mark.asyncio
async def test_usecase_07_multitenant_qos_noisy_neighbor() -> None:
    """Verify Use Case 07 Multi-tenant QoS contention and SLA audit with rate-limiting."""
    status = await run_multitenant_qos_simulation(
        tenant_a_ops=50,
        tenant_b_mb=4,
        target_uri=None,
        sla_threshold_ms=10.0,
        qos_throttle=True,
    )
    assert status == 0


def test_usecase_08_chaos_node_failure() -> None:
    """Verify Use Case 08 Distributed node failure with homogeneous and heterogeneous topologies."""
    status_homo = run_chaos_simulation(
        initial_nodes=8,
        cores_per_node=4,
        failed_nodes=2,
        total_target_size_gb=128,
        heterogeneous=False,
    )
    assert status_homo == 0

    status_hetero = run_chaos_simulation(
        initial_nodes=6,
        cores_per_node=8,
        failed_nodes=2,
        total_target_size_gb=64,
        heterogeneous=True,
    )
    assert status_hetero == 0


@pytest.mark.asyncio
async def test_usecase_09_storage_tiering_lifecycle() -> None:
    """Verify Use Case 09 Multi-tier storage lifecycle (Hot/Warm/Cold) and economics."""
    status = await run_storage_tiering_simulation(
        hot_ops=50,
        warm_mb=4,
        cold_chunks=2,
        dataset_tb=5.0,
    )
    assert status == 0


@pytest.mark.asyncio
async def test_usecase_10_tail_latency_microburst() -> None:
    """Verify Use Case 10 Tail-latency micro-burst and HDR histogram profiling."""
    status = await run_microburst_simulation(
        steady_ops=50,
        burst_cycles=2,
        burst_intensity=20,
        target_uri=None,
    )
    assert status == 0
