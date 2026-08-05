"""Cluster barrier synchronization state engine."""

import asyncio
import time
from typing import Any, Dict


class ClusterSyncServicer:
    """Handles node barrier readiness and synchronized release."""

    def __init__(self, expected_node_count: int, sync_lead_time_ms: int = 500) -> None:
        self._expected_node_count = expected_node_count
        self._sync_lead_time_ms = sync_lead_time_ms
        self._ready_nodes: Dict[str, Any] = {}
        self._release_event = asyncio.Event()
        self._synchronized_start_us = 0

    async def SignalReady(self, request: Any, context: Any) -> Any:
        """Invoked by node daemons when local ring buffers and io_uring queues are ready."""
        node_id = getattr(request, "node_id", "local_node")
        self._ready_nodes[node_id] = request

        # If all nodes report PREPARED, release barrier with future epoch timestamp
        if len(self._ready_nodes) >= self._expected_node_count:
            # Set synchronized start in the future to absorb network latency
            future_epoch_us = int((time.time() * 1_000_000) + (self._sync_lead_time_ms * 1_000))
            self._synchronized_start_us = future_epoch_us
            self._release_event.set()

        # Await barrier release event
        await self._release_event.wait()

        # Mock response object for python-level mock (without protobuf compiled)
        class WaitResponse:
            release = True
            synchronized_start_us = self._synchronized_start_us

        return WaitResponse()
