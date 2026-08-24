"""Use Case 05: High-Density AI Embedding & Object Store Ingestion Simulation.

Demonstrates unified target adapter abstraction for simulating vector embedding database
upserts/queries (Milvus/Pinecone/Qdrant) and S3 multipart object store ingestion.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

# Ensure steve package is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from steve.adapters.base import TargetDescriptor  # noqa: E402
from steve.adapters.factory import AdapterFactory  # noqa: E402
from steve.payload.buffer_pool import BufferPool  # noqa: E402
from steve.validation.metric_collector import MetricCollector  # noqa: E402


async def run_ai_vector_s3_simulation(
    vector_ops: int = 1000,
    vector_queries: int = 200,
    s3_chunks: int = 20,
    dimension: int = 1536,
    top_k: int = 10,
    query_concurrency: int = 8,
) -> int:
    """Execute asynchronous Vector DB and S3 ingestion simulations."""
    print("=" * 80)
    print("  STEVE USE CASE 05: AI Vector Embeddings & S3 Object Store Ingestion")
    print("=" * 80)

    # 1. Vector Database Ingestion & Query Simulation
    vector_uri = "vector://prod_embeddings_collection"
    print(f"\n[*] Initializing Vector Adapter for: {vector_uri}")
    vector_adapter = AdapterFactory.create(vector_uri)
    await vector_adapter.initialize({"dimension": dimension, "metric": "cosine", "top_k": top_k})

    upsert_collector = MetricCollector()
    query_collector = MetricCollector()
    pool = BufferPool(buffer_count=max(8, query_concurrency * 2), buffer_size=4096)

    try:
        vector_target = TargetDescriptor(
            endpoint_uri=vector_uri, resource_path="prod_embeddings_collection"
        )

        print(f"[*] Executing {vector_ops:,} vector upserts (dim={dimension}, 4KB batches)...")
        t0_upsert = time.perf_counter_ns()
        total_vector_bytes = 0
        for i in range(vector_ops):
            buf = pool.acquire(i % pool.buffer_count)
            op_t0 = time.perf_counter_ns()
            written = await vector_adapter.write(vector_target, offset=i * 4096, payload=buf)
            total_vector_bytes += written
            lat = time.perf_counter_ns() - op_t0
            upsert_collector.record_latency(lat)
            upsert_collector.record_bytes(written)

        await vector_adapter.flush(vector_target)
        upsert_duration = max((time.perf_counter_ns() - t0_upsert) / 1e9, 1e-9)
        upsert_iops = vector_ops / upsert_duration
        upsert_mb = total_vector_bytes / (1024 * 1024)

        # Simulated Vector Similarity Queries (Top-K ANN Search with async concurrency)
        print(
            f"[*] Executing {vector_queries:,} nearest-neighbor searches "
            f"(k={top_k}, concurrency={query_concurrency})..."
        )
        t0_query = time.perf_counter_ns()

        async def _query_worker(start_idx: int, count: int) -> None:
            for idx in range(start_idx, start_idx + count):
                buf = pool.acquire(idx % pool.buffer_count)
                op_t0 = time.perf_counter_ns()
                read_bytes = await vector_adapter.read(vector_target, offset=idx * 4096, buffer=buf)
                lat = time.perf_counter_ns() - op_t0
                query_collector.record_latency(lat)
                query_collector.record_bytes(read_bytes)

        # Distribute query workload across concurrent coroutines
        batch_size = max(1, vector_queries // query_concurrency)
        tasks = []
        for c in range(query_concurrency):
            c_start = c * batch_size
            c_count = batch_size if c < query_concurrency - 1 else vector_queries - c_start
            if c_count > 0:
                tasks.append(_query_worker(c_start, c_count))

        await asyncio.gather(*tasks)
        query_duration = max((time.perf_counter_ns() - t0_query) / 1e9, 1e-9)
        query_qps = vector_queries / query_duration

        # 2. S3 Object Store Simulation
        s3_uri = "s3://ai-model-checkpoints-us-east-1/llama3-70b-weights"
        print(f"\n[*] Initializing S3 Multipart Adapter for: {s3_uri}")
        s3_adapter = AdapterFactory.create(s3_uri)
        await s3_adapter.initialize({"region": "us-east-1", "multipart_threshold_mb": 5})

        s3_pool = BufferPool(buffer_count=4, buffer_size=1048576)  # 1MB chunks
        s3_collector = MetricCollector()

        try:
            s3_target = TargetDescriptor(
                endpoint_uri=s3_uri,
                resource_path="ai-model-checkpoints-us-east-1/llama3-70b-weights",
            )

            print(f"[*] Streaming {s3_chunks} x 1MB multipart chunks to object store...")
            t0_s3 = time.perf_counter_ns()
            total_s3_bytes = 0
            for i in range(s3_chunks):
                chunk_buf = s3_pool.acquire(i)
                op_t0 = time.perf_counter_ns()
                w = await s3_adapter.write(s3_target, offset=i * 1048576, payload=chunk_buf)
                total_s3_bytes += w
                lat = time.perf_counter_ns() - op_t0
                s3_collector.record_latency(lat)
                s3_collector.record_bytes(w)

            await s3_adapter.flush(s3_target)
            s3_duration = max((time.perf_counter_ns() - t0_s3) / 1e9, 1e-9)
            s3_gbps = (total_s3_bytes * 8) / s3_duration / 1e9
        finally:
            s3_pool.close()

    finally:
        pool.close()

    u_p50 = upsert_collector.percentile_ms(0.50)
    u_p99 = upsert_collector.percentile_ms(0.99)
    q_p50 = query_collector.percentile_ms(0.50)
    q_p99 = query_collector.percentile_ms(0.99)
    s_p99 = s3_collector.percentile_ms(0.99)

    print("\n+--------------------------------------------------------------------------------+")
    print("| AI VECTOR & S3 MULTI-TARGET WORKLOAD SUMMARY                                   |")
    print("+--------------------------------------------------------------------------------+")
    print(f"| Vector Upsert Throughput:   {upsert_iops:>16,.1f} upserts/sec                    |")
    print(f"| Vector Upsert Volume:       {upsert_mb:>16.2f} MB                             |")
    print(f"| Vector Upsert Latency (p50):{u_p50:>16.3f} ms                             |")
    print(f"| Vector Upsert Latency (p99):{u_p99:>16.3f} ms                             |")
    qps_str = f"{query_qps:,.1f} QPS (c={query_concurrency})"
    print(f"| Vector Query Rate (QPS):    {qps_str:>16}                             |")
    print(f"| Vector Query Latency (p50): {q_p50:>16.3f} ms                             |")
    print(f"| Vector Query Latency (p99): {q_p99:>16.3f} ms                             |")
    print(f"| S3 Ingestion Rate:          {s3_gbps:>16.2f} Gbps                           |")
    print(f"| S3 Chunk Latency (p99):     {s_p99:>16.3f} ms                             |")
    print("+--------------------------------------------------------------------------------+\n")

    return 0


def main() -> int:
    """Parse CLI options and execute AI workload simulation."""
    parser = argparse.ArgumentParser(
        description="STEVE Use Case 05: Vector & S3 Ingestion Simulator"
    )
    parser.add_argument(
        "--vector-ops",
        type=int,
        default=1000,
        help="Number of vector upsert operations (default: 1000)",
    )
    parser.add_argument(
        "--vector-queries",
        type=int,
        default=200,
        help="Number of vector similarity search queries (default: 200)",
    )
    parser.add_argument(
        "--s3-chunks",
        type=int,
        default=20,
        help="Number of 1MB S3 multipart chunks (default: 20)",
    )
    parser.add_argument(
        "--dimension",
        type=int,
        default=1536,
        help="Vector embedding dimension (default: 1536)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Top-K nearest neighbors to retrieve (default: 10)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=8,
        help="Async query client concurrency level (default: 8)",
    )

    args = parser.parse_args()
    return asyncio.run(
        run_ai_vector_s3_simulation(
            vector_ops=args.vector_ops,
            vector_queries=args.vector_queries,
            s3_chunks=args.s3_chunks,
            dimension=args.dimension,
            top_k=args.top_k,
            query_concurrency=args.concurrency,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
