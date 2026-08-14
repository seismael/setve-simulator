"""Use Case 05: High-Density AI Embedding & Object Store Ingestion Simulation.

Demonstrates unified target adapter abstraction for simulating vector embedding database
upserts (Milvus/Pinecone/Qdrant) and S3 multipart object store ingestion.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Ensure setve package is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from setve.adapters.base import TargetDescriptor  # noqa: E402
from setve.adapters.factory import AdapterFactory  # noqa: E402
from setve.payload.buffer_pool import BufferPool  # noqa: E402


async def run_ai_vector_s3_simulation(
    vector_ops: int = 1000,
    s3_chunks: int = 20,
) -> int:
    """Execute asynchronous Vector DB and S3 ingestion simulations."""
    print("=" * 80)
    print("  SETVE USE CASE 05: AI Vector Embeddings & S3 Object Store Ingestion")
    print("=" * 80)

    # 1. Vector Database Simulation
    vector_uri = "vector://prod_embeddings_collection"
    print(f"\n[*] Initializing Vector Adapter for: {vector_uri}")
    vector_adapter = AdapterFactory.create(vector_uri)
    await vector_adapter.initialize({"dimension": 1536, "metric": "cosine"})

    pool = BufferPool(buffer_count=4, buffer_size=4096)
    try:
        vector_target = TargetDescriptor(
            endpoint_uri=vector_uri, resource_path="prod_embeddings_collection"
        )

        print(f"[*] Executing {vector_ops:,} high-density vector upserts (4KB batch size)...")
        total_vector_bytes = 0
        for i in range(vector_ops):
            buf = pool.acquire(i)
            written = await vector_adapter.write(vector_target, offset=i * 4096, payload=buf)
            total_vector_bytes += written

        await vector_adapter.flush(vector_target)
        mb_ingested = total_vector_bytes / 1e6
        print(f"[+] Vector Ingestion: {vector_ops:,} ops | {mb_ingested:.2f} MB ingested.")

        # 2. S3 Object Store Simulation
        s3_uri = "s3://ai-model-checkpoints-us-east-1/llama3-70b-weights"
        print(f"\n[*] Initializing S3 Multipart Adapter for: {s3_uri}")
        s3_adapter = AdapterFactory.create(s3_uri)
        await s3_adapter.initialize({"region": "us-east-1", "multipart_threshold_mb": 5})

        s3_pool = BufferPool(buffer_count=4, buffer_size=1048576)  # 1MB chunks

        try:
            s3_target = TargetDescriptor(
                endpoint_uri=s3_uri,
                resource_path="ai-model-checkpoints-us-east-1/llama3-70b-weights",
            )

            print(f"[*] Streaming {s3_chunks} x 1MB multipart chunks to object store...")
            total_s3_bytes = 0
            for i in range(s3_chunks):
                chunk_buf = s3_pool.acquire(i)
                w = await s3_adapter.write(s3_target, offset=i * 1048576, payload=chunk_buf)
                total_s3_bytes += w

            await s3_adapter.flush(s3_target)
            mb_transferred = total_s3_bytes / 1e6
            print(f"[+] S3 Ingestion: {s3_chunks} chunks | {mb_transferred:.2f} MB transferred.")
        finally:
            s3_pool.close()

    finally:
        pool.close()

    v_cap = vector_adapter.capabilities()
    s_cap = s3_adapter.capabilities()
    print("\n+--------------------------------------------------------------------------------+")
    print("| ADAPTER CAPABILITIES SUMMARY                                                   |")
    print("+--------------------------------------------------------------------------------+")
    print(
        f"| Vector: max_ops={v_cap.max_concurrent_ops:<5} | "
        f"direct_io={str(v_cap.supports_direct_io):<5} | "
        f"block_size={v_cap.native_block_size:<6} |"
    )
    print(
        f"| S3:     max_ops={s_cap.max_concurrent_ops:<5} | "
        f"direct_io={str(s_cap.supports_direct_io):<5} | "
        f"block_size={s_cap.native_block_size:<6} |"
    )
    print("+--------------------------------------------------------------------------------+\n")

    return 0


def main() -> int:
    """Parse CLI options and execute AI workload simulation."""
    parser = argparse.ArgumentParser(
        description="SETVE Use Case 05: Vector & S3 Ingestion Simulator"
    )
    parser.add_argument(
        "--vector-ops",
        type=int,
        default=1000,
        help="Number of vector upsert operations (default: 1000)",
    )
    parser.add_argument(
        "--s3-chunks",
        type=int,
        default=20,
        help="Number of 1MB S3 multipart chunks (default: 20)",
    )

    args = parser.parse_args()
    return asyncio.run(
        run_ai_vector_s3_simulation(
            vector_ops=args.vector_ops,
            s3_chunks=args.s3_chunks,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
