"""Hot-path Adapter Benchmark Sanity Checks."""

import asyncio
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from steve.adapters.base import DirectBuffer, TargetDescriptor
from steve.adapters.posix import PosixDirectIOAdapter


def benchmark_posix_adapter() -> None:
    """Benchmark hot-path throughput for POSIX adapter interface."""
    adapter = PosixDirectIOAdapter()

    # Pre-allocate aligned test buffer (1 MB)
    block_size = 1048576
    raw_mem = bytearray(block_size)
    buf = DirectBuffer(address=4096, size=block_size, view=memoryview(raw_mem))

    # Benchmark memory alignment check
    start = time.perf_counter()
    iterations = 10000
    for _ in range(iterations):
        buf.assert_alignment(4096)
    elapsed = time.perf_counter() - start
    ns_per_op = (elapsed / iterations) * 1e9
    print(f"DirectBuffer alignment check: {ns_per_op:.2f} ns/op")

    # Benchmark async Direct I/O write throughput
    async def _run_benchmark() -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_file = Path(tmp_dir) / "benchmark_test.dat"
            desc = TargetDescriptor(endpoint_uri="file://local", resource_path=str(test_file))

            await adapter.initialize({})
            io_iters = 100
            t0 = time.perf_counter()
            for i in range(io_iters):
                await adapter.write(desc, i * block_size, buf)
            await adapter.flush(desc)
            t_write = time.perf_counter() - t0

            total_bytes = io_iters * block_size
            write_gbps = (total_bytes * 8) / (t_write * 1e9)
            total_mb = total_bytes / (1024**2)
            t_ms = t_write * 1000
            print(f"POSIX Adapter: {write_gbps:.2f} Gbps ({total_mb:.1f} MB in {t_ms:.1f} ms)")
            adapter.close()

    asyncio.run(_run_benchmark())


if __name__ == "__main__":
    benchmark_posix_adapter()
