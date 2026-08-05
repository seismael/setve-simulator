"""Hot-path Adapter Benchmark Sanity Checks."""

import time

from setve.adapters.base import DirectBuffer, TargetDescriptor
from setve.adapters.posix import PosixDirectIOAdapter


def benchmark_posix_adapter() -> None:
    """Benchmark hot-path throughput for POSIX adapter interface."""
    adapter = PosixDirectIOAdapter()
    buf = DirectBuffer(address=4096, size=1048576, view=memoryview(bytearray(1048576)))
    desc = TargetDescriptor(endpoint_uri="file://local", resource_path="/tmp/test.dat")

    start = time.perf_counter()
    iterations = 1000
    for _ in range(iterations):
        buf.assert_alignment(4096)
    elapsed = time.perf_counter() - start

    ns_per_op = (elapsed / iterations) * 1e9
    print(f"DirectBuffer alignment check: {ns_per_op:.2f} ns/op")


if __name__ == "__main__":
    benchmark_posix_adapter()
