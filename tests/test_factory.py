"""Tests for GoF AdapterFactory resolution."""

import pytest
import sys

from setve.adapters.factory import AdapterFactory
from setve.adapters.posix import PosixDirectIOAdapter
from setve.adapters.io_uring import IoUringTargetAdapter


def test_factory_resolves_posix() -> None:
    """Verify factory returns PosixDirectIOAdapter for posix:// scheme."""
    cls = AdapterFactory.get_adapter_class("posix:///mnt/data")
    assert cls is PosixDirectIOAdapter

    cls2 = AdapterFactory.get_adapter_class("file://local/test")
    assert cls2 is PosixDirectIOAdapter


def test_factory_resolves_iouring() -> None:
    """Verify factory returns appropriate adapter for iouring:// scheme."""
    cls = AdapterFactory.get_adapter_class("iouring:///dev/nvme0n1")
    if sys.platform == "win32":
        # Windows gracefully falls back
        assert cls is PosixDirectIOAdapter
    else:
        assert cls is IoUringTargetAdapter


def test_factory_raises_not_implemented() -> None:
    """Verify factory raises error for missing adapters."""
    with pytest.raises(NotImplementedError):
        AdapterFactory.get_adapter_class("s3://bucket/test")

    with pytest.raises(NotImplementedError):
        AdapterFactory.get_adapter_class("nvmeof://10.0.0.1:4420")
