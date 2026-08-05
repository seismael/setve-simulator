"""SIMD Payload Mutator Bounds Tests."""

from setve.payload.mutator import PySIMDPayloadMutator


def test_mutator_slice_bounds() -> None:
    """Verify mutator generates valid memory slices within allocated size."""
    mutator = PySIMDPayloadMutator(buffer_size=1048576)
    try:
        buf = mutator.apply_entropy(offset=0, block_size=4096, seed=42)
        assert buf.size == 4096
        assert len(buf.view) == 4096
        del buf  # Release memoryview exported pointer before close
    finally:
        mutator.close()
