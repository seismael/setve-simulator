"""Workload Pattern Profiles."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WorkloadProfile:
    """Pre-configured simulation workload profile blueprint."""

    name: str
    block_size: int
    entropy_ratio: float
    target_protocol: str


WORKLOAD_PROFILES = {
    "ai_prefill_large_seq": WorkloadProfile(
        name="AI Prefill Large Sequential",
        block_size=1048576,  # 1MB
        entropy_ratio=0.85,
        target_protocol="posix",
    ),
    "posix_random_4k": WorkloadProfile(
        name="POSIX Random 4K Block",
        block_size=4096,  # 4KB
        entropy_ratio=0.50,
        target_protocol="io_uring",
    ),
    "s3_multipart_stream": WorkloadProfile(
        name="S3 Multipart Stream",
        block_size=8388608,  # 8MB
        entropy_ratio=0.90,
        target_protocol="s3",
    ),
    "vector_embeddings_64b": WorkloadProfile(
        name="Vector Embeddings 64B",
        block_size=64,
        entropy_ratio=0.99,
        target_protocol="vector",
    ),
}
