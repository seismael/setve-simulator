"""Adapter Factory for dynamic TargetAdapter resolution."""

import os
import sys
from typing import Type

from setve.adapters.base import TargetAdapter
from setve.adapters.posix import PosixDirectIOAdapter
from setve.adapters.io_uring import IoUringTargetAdapter


class AdapterFactory:
    """GoF Factory for resolving target adapters based on URI schemes and OS support."""

    @staticmethod
    def get_adapter_class(target_uri: str) -> Type[TargetAdapter]:
        """Resolve the appropriate adapter class from the URI."""
        scheme = target_uri.split("://")[0].lower()

        if scheme in ("posix", "file"):
            return PosixDirectIOAdapter
            
        if scheme == "iouring":
            if sys.platform == "win32":
                print("WARNING: io_uring requested on Windows. Falling back to PosixDirectIOAdapter.")
                return PosixDirectIOAdapter
            return IoUringTargetAdapter
            
        if scheme == "s3":
            # Stub for future implementation
            raise NotImplementedError("S3 Target Adapter is not yet implemented.")

        if scheme == "nvmeof":
            # Stub for future implementation
            raise NotImplementedError("NVMe-oF Target Adapter is not yet implemented.")

        # Default fallback
        return PosixDirectIOAdapter
