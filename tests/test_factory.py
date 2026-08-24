"""Tests for GoF AdapterFactory resolution."""

import sys

import pytest

from steve.adapters.factory import AdapterFactory
from steve.adapters.io_uring import IoUringTargetAdapter
from steve.adapters.posix import PosixDirectIOAdapter
from steve.adapters.s3 import S3TargetAdapter
from steve.adapters.vector import VectorTargetAdapter


def test_factory_resolves_posix() -> None:
    """Verify factory returns PosixDirectIOAdapter for posix:// and file:// schemes."""
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


def test_factory_resolves_s3() -> None:
    """Verify factory returns S3TargetAdapter for s3:// scheme."""
    cls = AdapterFactory.get_adapter_class("s3://bucket/test")
    assert cls is S3TargetAdapter


def test_factory_resolves_vector() -> None:
    """Verify factory returns VectorTargetAdapter for vector:// and embedding:// schemes."""
    cls = AdapterFactory.get_adapter_class("vector://collection/test")
    assert cls is VectorTargetAdapter

    cls2 = AdapterFactory.get_adapter_class("embedding://collection/test")
    assert cls2 is VectorTargetAdapter


def test_factory_raises_not_implemented() -> None:
    """Verify factory raises error for unhandled or missing protocols."""
    with pytest.raises(NotImplementedError):
        AdapterFactory.get_adapter_class("nvmeof://10.0.0.1:4420")
