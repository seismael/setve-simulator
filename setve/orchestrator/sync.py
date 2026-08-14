"""Cluster barrier synchronization state engine."""

import asyncio
import time
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class BarrierWaitResponse:
    """Barrier synchronization response containing synchronized start timestamp."""

    release: bool
    synchronized_start_us: int


class ClusterSyncServicer:
    """Handles node barrier readiness and synchronized release."""

    def __init__(self, expected_node_count: int, sync_lead_time_ms: int = 500) -> None:
        self._expected_node_count = expected_node_count
        self._sync_lead_time_ms = sync_lead_time_ms
        self._ready_nodes: dict[str, Any] = {}
        self._release_event = asyncio.Event()
        self._synchronized_start_us = 0

    async def signal_ready(self, request: Any, context: Any = None) -> BarrierWaitResponse:
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

        return BarrierWaitResponse(
            release=True,
            synchronized_start_us=self._synchronized_start_us,
        )

    async def SignalReady(  # noqa: N802
        self, request: Any, context: Any = None
    ) -> BarrierWaitResponse:
        """gRPC PascalCase compatibility alias for signal_ready."""
        return await self.signal_ready(request, context)
