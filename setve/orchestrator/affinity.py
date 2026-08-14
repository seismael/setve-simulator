"""Hardware CPU Topology & Core Affinity Utilities."""

import contextlib
import os


def pin_to_core(core_id: int) -> None:
    """Pin active process to designated physical CPU core ID."""
    if hasattr(os, "sched_setaffinity"):
        with contextlib.suppress(OSError):
            os.sched_setaffinity(0, {core_id})


def available_cores() -> list[int]:
    """Return available CPU core IDs on host platform."""
    if hasattr(os, "sched_getaffinity"):
        with contextlib.suppress(OSError):
            return list(os.sched_getaffinity(0))
    return list(range(os.cpu_count() or 1))
