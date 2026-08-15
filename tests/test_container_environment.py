"""Test Suite for Container Environment Execution & Local Service Interoperability."""

from __future__ import annotations

import http.client
import os
import threading
import time

import pytest

from setve.adapters.factory import AdapterFactory
from usecases.usecase_03_prometheus_monitoring import run_prometheus_monitoring
from usecases.usecase_05_ai_vector_s3 import run_ai_vector_s3_simulation


def test_container_environment_variable_overrides() -> None:
    """Verify that SETVE respects containerized environment variables."""
    os.environ["SETVE_ENV"] = "container"
    os.environ["SETVE_S3_ENDPOINT"] = "http://minio:9000"
    os.environ["SETVE_S3_BUCKET"] = "setve-test-bucket"

    s3_adapter = AdapterFactory.create("s3://setve-test-bucket/model_checkpoint")
    assert s3_adapter is not None
    assert not s3_adapter.capabilities().supports_direct_io
    assert s3_adapter.capabilities().supports_async_cancellation


@pytest.mark.asyncio
async def test_container_s3_and_vector_usecase_execution() -> None:
    """Verify Use Case 05 runs cleanly under container environment settings."""
    exit_code = await run_ai_vector_s3_simulation(
        vector_ops=100,
        vector_queries=20,
        s3_chunks=5,
        dimension=256,
        top_k=5,
        query_concurrency=2,
    )
    assert exit_code == 0


def test_live_prometheus_server_and_client_scrape() -> None:
    """Verify live Prometheus HTTP server responds with valid exposition text on port 9100."""
    port = 9188
    # Start server in background thread
    server_thread = threading.Thread(
        target=run_prometheus_monitoring,
        kwargs={
            "duration_seconds": 0.5,
            "target_throughput_gbps": 1.0,
            "serve_port": port,
            "serve_duration": 4.0,
        },
        daemon=True,
    )
    server_thread.start()

    body = ""
    # Poll with retries until server starts and responds
    for _ in range(50):
        time.sleep(0.1)
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=1.0)
            conn.request("GET", "/metrics")
            resp = conn.getresponse()
            if resp.status == 200:
                body = resp.read().decode("utf-8")
                conn.close()
                break
            conn.close()
        except Exception:
            pass

    server_thread.join(timeout=6.0)
    assert "setve_cluster_ops_total" in body
    assert "setve_cluster_bytes_total" in body
