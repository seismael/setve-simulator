"""Verification test suite for all production use case scripts."""

from __future__ import annotations

import pytest

from usecases.usecase_01_storage_stress import run_storage_stress
from usecases.usecase_02_dedup_compression import run_dedup_compression_bench
from usecases.usecase_03_prometheus_monitoring import run_prometheus_monitoring
from usecases.usecase_04_ebpf_triangulation import run_ebpf_triangulation
from usecases.usecase_05_ai_vector_s3 import run_ai_vector_s3_simulation


def test_usecase_01_storage_stress() -> None:
    """Verify Use Case 01 executes successfully."""
    status = run_storage_stress(
        target_path=None,
        block_size_bytes=4096,
        target_throughput_gbps=1.0,
        duration_seconds=0.5,
        entropy_ratio=0.5,
        num_cores=1,
    )
    assert status == 0


def test_usecase_02_dedup_compression() -> None:
    """Verify Use Case 02 executes successfully across entropy sweeps."""
    status = run_dedup_compression_bench(
        buffer_size_mb=1,
        iterations=10,
    )
    assert status == 0


def test_usecase_03_prometheus_monitoring() -> None:
    """Verify Use Case 03 generates valid Prometheus and JSON metrics."""
    status = run_prometheus_monitoring(
        duration_seconds=0.5,
        target_throughput_gbps=1.0,
    )
    assert status == 0


def test_usecase_04_ebpf_triangulation_pass() -> None:
    """Verify Use Case 04 passes when metric drift is zero."""
    status = run_ebpf_triangulation(
        simulated_transfer_mb=100,
        skew_drift_bytes=0,
        tolerance_percent=0.1,
    )
    assert status == 0


def test_usecase_04_ebpf_triangulation_fail() -> None:
    """Verify Use Case 04 returns non-zero exit status on excessive metric drift."""
    status = run_ebpf_triangulation(
        simulated_transfer_mb=100,
        skew_drift_bytes=10_000_000,  # 10 MB drift on 100 MB -> 10% skew > 0.1% tolerance
        tolerance_percent=0.1,
    )
    assert status == 1


@pytest.mark.asyncio
async def test_usecase_05_ai_vector_s3() -> None:
    """Verify Use Case 05 executes vector and S3 ingestion passes."""
    status = await run_ai_vector_s3_simulation(
        vector_ops=50,
        s3_chunks=5,
    )
    assert status == 0
