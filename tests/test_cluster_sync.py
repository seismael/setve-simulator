"""Tests for ClusterSyncServicer barrier synchronization protocol."""

import asyncio
from types import SimpleNamespace

import pytest

from steve.orchestrator.sync import ClusterSyncServicer


@pytest.mark.asyncio
async def test_cluster_barrier_synchronization() -> None:
    """Verify ClusterSyncServicer releases only when all expected nodes report prepared."""
    servicer = ClusterSyncServicer(expected_node_count=2, sync_lead_time_ms=100)

    req1 = SimpleNamespace(node_id="node-1", core_count=8)
    req2 = SimpleNamespace(node_id="node-2", core_count=8)

    # Launch task 1 (waiting for node 2)
    task1 = asyncio.create_task(servicer.signal_ready(req1))
    await asyncio.sleep(0.01)
    assert not task1.done()

    # Launch task 2 (triggers release)
    task2 = asyncio.create_task(servicer.signal_ready(req2))

    resp1, resp2 = await asyncio.gather(task1, task2)

    assert resp1.release is True
    assert resp2.release is True
    assert resp1.synchronized_start_us == resp2.synchronized_start_us
    assert resp1.synchronized_start_us > 0


@pytest.mark.asyncio
async def test_grpc_pascal_case_alias() -> None:
    """Verify SignalReady PascalCase method acts identically."""
    servicer = ClusterSyncServicer(expected_node_count=1, sync_lead_time_ms=50)
    req = SimpleNamespace(node_id="node-single")

    resp = await servicer.SignalReady(req)
    assert resp.release is True
    assert resp.synchronized_start_us > 0
