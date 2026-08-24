"""STEVE Use Case 06: AI LLM KV-Cache & Model Checkpointing Simulation.

Simulates heterogeneous AI inference and training workloads:
1. Prefill Phase: High-bandwidth sequential prompt ingestion (1 MB chunks).
2. Decode Phase: High-concurrency, low-latency KV-cache token updates (4 KB / 16 KB blocks).
3. Checkpoint Burst: Bulk asynchronous model checkpoint dump to storage backend.
"""

import argparse
import asyncio
import contextlib
import sys
import tempfile
import time
from pathlib import Path

# Ensure steve package is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from steve.adapters.base import TargetDescriptor  # noqa: E402
from steve.adapters.factory import AdapterFactory  # noqa: E402
from steve.payload.buffer_pool import BufferPool  # noqa: E402
from steve.payload.mutator import PySIMDPayloadMutator  # noqa: E402
from steve.validation.metric_collector import MetricCollector  # noqa: E402


async def run_ai_kv_cache_simulation(
    prefill_mb: int = 128,
    decode_tokens: int = 2000,
    checkpoint_mb: int = 256,
    target_uri: str | None = None,
    page_block_kb: int = 16,
) -> int:
    """Execute multi-phase AI KV-cache prefill, decode, and checkpointing load."""
    print("=" * 80)
    print("  STEVE USE CASE 06: AI LLM KV-Cache & Model Checkpointing Simulation")
    print("=" * 80)

    cleanup_tmp = False
    tmp_dir = None
    if not target_uri:
        tmp_dir = tempfile.TemporaryDirectory()
        target_file = Path(tmp_dir.name) / "ai_sim_target.dat"
        target_uri = f"posix://{target_file}"
        cleanup_tmp = True
        print(f"[*] Target URI:            {target_uri} (Temporary Storage)")
    else:
        print(f"[*] Target URI:            {target_uri}")

    try:
        adapter = AdapterFactory.create(target_uri)
        await adapter.initialize({"direct_io": False})
        target = TargetDescriptor(endpoint_uri=target_uri, resource_path="ai_sim_target.dat")

        collector = MetricCollector()

        # 1. Prefill Phase (Prompt Token Ingestion)
        prefill_block_size = 1048576  # 1 MB
        prefill_blocks = max(1, prefill_mb)
        print(f"\n[Phase 1: Prefill] Ingesting {prefill_mb} MB prompt context (1 MB blocks)...")

        mutator = PySIMDPayloadMutator(prefill_block_size)

        t0_prefill = time.perf_counter_ns()
        for i in range(prefill_blocks):
            # Mutate with prompt embedding entropy
            buf = mutator.mutate_entropy_block(0, prefill_block_size, entropy_ratio=0.7, seed=i)
            op_t0 = time.perf_counter_ns()
            w = await adapter.write(target, offset=i * prefill_block_size, payload=buf)
            collector.record_latency(time.perf_counter_ns() - op_t0)
            collector.record_bytes(w)

        prefill_duration = max((time.perf_counter_ns() - t0_prefill) / 1e9, 1e-9)
        prefill_gbps = (prefill_mb * 1024 * 1024 * 8) / prefill_duration / 1e9
        prefill_ms = prefill_duration * 1000
        print(f"[+] Prefill Complete: {prefill_gbps:.2f} Gbps in {prefill_ms:.2f} ms")

        # 2. Decode Phase (Token Generation KV-Cache Random Access via PagedAttention)
        decode_block_size = page_block_kb * 1024  # PagedAttention physical block size
        print(
            f"\n[Phase 2: Decode] Generating {decode_tokens:,} tokens "
            f"({page_block_kb} KB PagedAttention KV-cache updates)..."
        )

        decode_collector = MetricCollector()
        decode_mutator = PySIMDPayloadMutator(decode_block_size)

        t0_decode = time.perf_counter_ns()
        max_context_bytes = max(prefill_mb * 1024 * 1024, decode_block_size)
        for step in range(decode_tokens):
            buf = decode_mutator.apply_entropy(0, decode_block_size, seed=step)
            op_t0 = time.perf_counter_ns()
            # Non-contiguous virtual block table offset mapping (PagedAttention)
            virtual_block_id = (step * 37) % max(1, max_context_bytes // decode_block_size)
            offset = virtual_block_id * decode_block_size
            w = await adapter.write(target, offset=offset, payload=buf)
            elapsed = time.perf_counter_ns() - op_t0
            decode_collector.record_latency(elapsed)
            decode_collector.record_bytes(w)

        decode_duration = max((time.perf_counter_ns() - t0_decode) / 1e9, 1e-9)
        tokens_per_sec = decode_tokens / decode_duration
        decode_p50 = decode_collector.percentile_ms(0.50)
        decode_p90 = decode_collector.percentile_ms(0.90)
        decode_p99 = decode_collector.percentile_ms(0.99)
        print(
            f"[+] Decode Complete: {tokens_per_sec:.1f} tokens/s | "
            f"p50={decode_p50:.3f}ms | p99={decode_p99:.3f}ms"
        )

        # 3. Checkpointing Phase (Bulk Weights Dump)
        print(f"\n[Phase 3: Checkpoint] Flushing {checkpoint_mb} MB model weights to storage...")
        ckpt_pool = BufferPool(buffer_count=4, buffer_size=prefill_block_size)
        t0_ckpt = time.perf_counter_ns()
        try:
            for i in range(checkpoint_mb):
                buf = ckpt_pool.acquire(i % ckpt_pool.buffer_count)
                await adapter.write(target, offset=i * prefill_block_size, payload=buf)
            await adapter.flush(target)
        finally:
            ckpt_pool.close()

        ckpt_duration = max((time.perf_counter_ns() - t0_ckpt) / 1e9, 1e-9)
        ckpt_rate_gbps = (checkpoint_mb * 1024 * 1024 * 8) / ckpt_duration / 1e9
        print(f"[+] Checkpoint Complete: {ckpt_rate_gbps:.2f} Gbps in {ckpt_duration:.2f} s")

        ttft_ms = prefill_ms
        itl_p50_ms = decode_p50
        itl_p99_ms = decode_p99

        # Summary Report
        print(
            "\n+--------------------------------------------------------------------------------+"
        )
        print("| AI LLM INFERENCE & TRAINING STORAGE SUMMARY                                    |")
        print("+--------------------------------------------------------------------------------+")
        print(
            f"| Prefill Ingest Rate:        {prefill_gbps:>16.2f} Gbps                            |"
        )
        print(f"| Time-To-First-Token (TTFT): {ttft_ms:>16.2f} ms                              |")
        tok_rate_str = f"{tokens_per_sec:,.1f} tok/s"
        print(f"| Decode Token Rate:          {tok_rate_str:>16}                            |")
        page_str = f"{page_block_kb} KB"
        print(f"| PagedAttention Block Size:  {page_str:>16}                               |")
        print(f"| Inter-Token Latency (p50):  {itl_p50_ms:>16.3f} ms                            |")
        print(f"| Inter-Token Latency (p90):  {decode_p90:>16.3f} ms                            |")
        print(f"| Inter-Token Latency (p99):  {itl_p99_ms:>16.3f} ms                            |")
        ckpt_str = f"{ckpt_rate_gbps:.2f} Gbps"
        print(f"| Checkpoint Flush Bandwidth: {ckpt_str:>16}                           |")
        print(
            "+--------------------------------------------------------------------------------+\n"
        )

        return 0
    finally:
        if cleanup_tmp and tmp_dir is not None:
            with contextlib.suppress(Exception):
                tmp_dir.cleanup()


def main() -> int:
    """Parse CLI options and execute AI KV-cache simulation."""
    parser = argparse.ArgumentParser(
        description="STEVE Use Case 06: AI LLM KV-Cache & Model Checkpointing Simulation"
    )
    parser.add_argument(
        "--prefill-mb",
        type=int,
        default=64,
        help="Volume of prefill context data to ingest in MB (default: 64)",
    )
    parser.add_argument(
        "--tokens",
        type=int,
        default=1000,
        help="Number of decode token generation iterations (default: 1000)",
    )
    parser.add_argument(
        "--checkpoint-mb",
        type=int,
        default=128,
        help="Volume of model checkpoint weights to flush in MB (default: 128)",
    )
    parser.add_argument(
        "--target-uri",
        type=str,
        default=None,
        help="Target storage URI (default: temporary storage file)",
    )
    parser.add_argument(
        "--page-kb",
        type=int,
        default=16,
        help="PagedAttention block size in KB (default: 16)",
    )
    args = parser.parse_args()

    return asyncio.run(
        run_ai_kv_cache_simulation(
            prefill_mb=args.prefill_mb,
            decode_tokens=args.tokens,
            checkpoint_mb=args.checkpoint_mb,
            target_uri=args.target_uri,
            page_block_kb=args.page_kb,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
