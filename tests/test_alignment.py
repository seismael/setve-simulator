"""4096-byte and 64-byte Memory Alignment Tests."""

import pytest

from steve.adapters.base import DirectBuffer


def test_buffer_alignment_pass() -> None:
    """Verify aligned DirectBuffer passes alignment assertions."""
    buf = DirectBuffer(address=8192, size=4096, view=memoryview(bytearray(4096)))
    buf.assert_alignment(4096)
    buf.assert_alignment(64)


def test_buffer_alignment_fail() -> None:
    """Verify misaligned DirectBuffer raises ValueError."""
    buf = DirectBuffer(address=8193, size=4096, view=memoryview(bytearray(4096)))
    with pytest.raises(ValueError, match="violates 4096-byte alignment"):
        buf.assert_alignment(4096)
