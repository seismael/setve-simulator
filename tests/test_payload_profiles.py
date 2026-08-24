"""Unit tests for WorkloadPattern Profiles and WorkloadProfile configurations."""

from steve.payload.profiles import WORKLOAD_PROFILES, WorkloadProfile


def test_workload_profiles_registry() -> None:
    """Verify all standard workload pattern profiles are valid and correctly typed."""
    assert len(WORKLOAD_PROFILES) >= 4

    # 1. AI Prefill profile
    ai_prof = WORKLOAD_PROFILES["ai_prefill_large_seq"]
    assert isinstance(ai_prof, WorkloadProfile)
    assert ai_prof.block_size == 1048576  # 1MB
    assert ai_prof.entropy_ratio == 0.85
    assert ai_prof.target_protocol == "posix"
    assert "AI Prefill" in ai_prof.name

    # 2. POSIX random 4K profile
    posix_prof = WORKLOAD_PROFILES["posix_random_4k"]
    assert posix_prof.block_size == 4096
    assert posix_prof.entropy_ratio == 0.50
    assert posix_prof.target_protocol == "io_uring"

    # 3. S3 Multipart stream profile
    s3_prof = WORKLOAD_PROFILES["s3_multipart_stream"]
    assert s3_prof.block_size == 8388608  # 8MB
    assert s3_prof.entropy_ratio == 0.90
    assert s3_prof.target_protocol == "s3"

    # 4. Vector embeddings profile
    vec_prof = WORKLOAD_PROFILES["vector_embeddings_64b"]
    assert vec_prof.block_size == 64
    assert vec_prof.entropy_ratio == 0.99
    assert vec_prof.target_protocol == "vector"
