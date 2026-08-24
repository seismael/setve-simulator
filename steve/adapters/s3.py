"""S3 Object Storage Target Adapter."""

from typing import Any

from steve.adapters.base import (
    AdapterCapabilities,
    DirectBuffer,
    TargetAdapter,
    TargetDescriptor,
)


class S3TargetAdapter(TargetAdapter):
    """High-throughput object store adapter for HTTP multipart streaming."""

    def __init__(self) -> None:
        self._capabilities = AdapterCapabilities(
            supports_direct_io=False,
            supports_async_cancellation=True,
            max_concurrent_ops=512,
            native_block_size=5242880,  # 5MB S3 part minimum
        )

    async def initialize(self, config: dict[str, Any]) -> None:
        """Initialize S3 client session credentials and endpoint config."""
        pass

    async def write(self, target: TargetDescriptor, offset: int, payload: DirectBuffer) -> int:
        """Submit multipart upload chunk."""
        return len(payload.view)

    async def read(self, target: TargetDescriptor, offset: int, buffer: DirectBuffer) -> int:
        """Fetch byte range object stream."""
        return len(buffer.view)

    async def flush(self, target: TargetDescriptor) -> None:
        """Complete active multipart upload session."""
        pass

    def capabilities(self) -> AdapterCapabilities:
        """Return S3 adapter capabilities."""
        return self._capabilities
