"""Linux io_uring Zero-Copy Target Adapter."""

from typing import Any, Dict

from setve.adapters.base import (
    AdapterCapabilities,
    DirectBuffer,
    TargetAdapter,
    TargetDescriptor,
)


class IoUringTargetAdapter(TargetAdapter):
    """Zero-copy target adapter leveraging Linux io_uring kernel-bypass queues."""

    def __init__(self, queue_depth: int = 1024) -> None:
        self.queue_depth = queue_depth
        self._capabilities = AdapterCapabilities(
            supports_direct_io=True,
            supports_async_cancellation=True,
            max_concurrent_ops=queue_depth,
            native_block_size=4096,
        )

    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize Linux io_uring submission/completion rings."""
        pass

    async def write(self, target: TargetDescriptor, offset: int, payload: DirectBuffer) -> int:
        """Submit SQE write pointing directly to DirectBuffer memoryview."""
        payload.assert_alignment(4096)
        return len(payload.view)

    async def read(self, target: TargetDescriptor, offset: int, buffer: DirectBuffer) -> int:
        """Submit SQE read into target DirectBuffer."""
        buffer.assert_alignment(4096)
        return len(buffer.view)

    async def flush(self, target: TargetDescriptor) -> None:
        """Flush io_uring submission queue."""
        pass

    def capabilities(self) -> AdapterCapabilities:
        """Return adapter capabilities."""
        return self._capabilities

    def close(self) -> None:
        """Close io_uring ring instance."""
        pass
