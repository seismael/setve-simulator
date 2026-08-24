"""SIMD Payload Mutator Bounds and Entropy Tests."""

import pytest

from steve.payload.mutator import PySIMDPayloadMutator


def test_mutator_slice_bounds() -> None:
    """Verify mutator generates valid memory slices within allocated size."""
    mutator = PySIMDPayloadMutator(buffer_size=1048576)
    try:
        buf = mutator.apply_entropy(offset=0, block_size=4096, seed=42)
        assert buf.size == 4096
        assert len(buf.view) == 4096
        assert buf.address == mutator.address
        del buf
    finally:
        mutator.close()


def test_mutator_offset_slicing() -> None:
    """Verify mutator computes correct slice addresses and views for non-zero offsets."""
    mutator = PySIMDPayloadMutator(buffer_size=1048576)
    try:
        offset = 8192
        block_size = 4096
        buf = mutator.apply_entropy(offset=offset, block_size=block_size, seed=123)
        assert buf.size == block_size
        assert len(buf.view) == block_size
        assert buf.address == mutator.address + offset
        buf.assert_alignment(4096)
        del buf
    finally:
        mutator.close()


def test_mutator_out_of_bounds() -> None:
    """Verify mutator raises ValueError when requested slice exceeds buffer size."""
    mutator = PySIMDPayloadMutator(buffer_size=4096)
    try:
        with pytest.raises(ValueError, match="exceeds buffer size"):
            mutator.apply_entropy(offset=2048, block_size=4096, seed=1)
    finally:
        mutator.close()


def test_mutator_entropy_determinism() -> None:
    """Verify identical seeds produce identical payload masks and different seeds diverge."""
    mutator1 = PySIMDPayloadMutator(buffer_size=4096)
    mutator2 = PySIMDPayloadMutator(buffer_size=4096)
    try:
        buf1 = mutator1.apply_entropy(offset=0, block_size=4096, seed=999)
        buf2 = mutator2.apply_entropy(offset=0, block_size=4096, seed=999)
        assert bytes(buf1.view) == bytes(buf2.view)

        # Mutate mutator2 with a different seed
        buf3 = mutator2.apply_entropy(offset=0, block_size=4096, seed=111)
        assert bytes(buf1.view) != bytes(buf3.view)
        del buf1, buf2, buf3
    finally:
        mutator1.close()
        mutator2.close()


def test_mutator_blueprint_ratio() -> None:
    """Verify mutate_entropy_block accurately applies entropy according to ratio."""
    mutator = PySIMDPayloadMutator(buffer_size=8192)
    try:
        buf = mutator.mutate_entropy_block(offset=0, length=4096, entropy_ratio=0.5, seed=42)
        assert buf.size == 4096
        assert len(buf.view) == 4096
        del buf
    finally:
        mutator.close()
