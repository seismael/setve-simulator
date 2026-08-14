"""Adapter Factory for dynamic TargetAdapter resolution."""

import logging
import sys

from setve.adapters.base import TargetAdapter
from setve.adapters.io_uring import IoUringTargetAdapter
from setve.adapters.posix import PosixDirectIOAdapter
from setve.adapters.s3 import S3TargetAdapter
from setve.adapters.vector import VectorTargetAdapter

logger = logging.getLogger("setve.adapters.factory")


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

        if scheme == "nvmeof":
            raise NotImplementedError("NVMe-oF Target Adapter is not yet implemented.")

        # Default fallback
        return PosixDirectIOAdapter
