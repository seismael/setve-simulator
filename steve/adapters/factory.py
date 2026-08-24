"""Adapter Factory for dynamic TargetAdapter resolution."""

import logging
import sys

from steve.adapters.base import TargetAdapter
from steve.adapters.io_uring import IoUringTargetAdapter
from steve.adapters.posix import PosixDirectIOAdapter
from steve.adapters.s3 import S3TargetAdapter
from steve.adapters.vector import VectorTargetAdapter

logger = logging.getLogger("steve.adapters.factory")


class AdapterFactory:
    """GoF Factory for resolving target adapters based on URI schemes and OS support."""

    @staticmethod
    def get_adapter_class(target_uri: str) -> type[TargetAdapter]:
        """Resolve the appropriate adapter class from the URI."""
        scheme = target_uri.split("://")[0].lower()

        if scheme in ("posix", "file"):
            return PosixDirectIOAdapter

        if scheme in ("iouring", "io_uring"):
            if sys.platform == "win32":
                logger.warning(
                    "io_uring requested on Windows host. "
                    "Gracefully falling back to PosixDirectIOAdapter."
                )
                return PosixDirectIOAdapter
            return IoUringTargetAdapter

        if scheme == "s3":
            return S3TargetAdapter

        if scheme in ("vector", "embedding"):
            return VectorTargetAdapter

        raise NotImplementedError(
            f"Unsupported target URI scheme '{scheme}'. "
            "Supported schemes: posix://, file://, iouring://, s3://, vector://"
        )

    @classmethod
    def create(cls, target_uri: str, **kwargs: object) -> TargetAdapter:
        """Instantiate and return target adapter for URI scheme."""
        adapter_cls = cls.get_adapter_class(target_uri)
        return adapter_cls(**kwargs)
