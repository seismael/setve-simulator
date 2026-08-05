"""Hardware CPU Topology & Core Affinity Utilities."""

import os
from typing import List


def pin_to_core(core_id: int) -> None:
    """Pin active process to designated physical CPU core ID."""
    if hasattr(os, "sched_setaffinity"):
        os.sched_setaffinity(0, {core_id})


def available_cores() -> List[int]:
    """Return available CPU core IDs on host platform."""
    if hasattr(os, "sched_getaffinity"):
        return list(os.sched_getaffinity(0))
    return list(range(os.cpu_count() or 1))
