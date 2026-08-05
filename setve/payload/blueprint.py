"""Workload Blueprint Domain Model."""

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True, slots=True)
class WorkloadBlueprint:
    """Domain model representing a declarative SETVE execution plan."""
    run_id: str
    target_uri: str
    block_size_bytes: int = 1048576
    entropy_ratio: float = 0.8
    target_throughput_gbps: int = 100
    duration_seconds: int = 30
    global_seed: int = 42

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkloadBlueprint":
        """Parse blueprint from a configuration dictionary (e.g., YAML)."""
        return cls(
            run_id=data.get("run_id", "sim-default-run"),
            target_uri=data["target_uri"],
            block_size_bytes=data.get("block_size_bytes", 1048576),
            entropy_ratio=data.get("entropy_ratio", 0.8),
            target_throughput_gbps=data.get("target_throughput_gbps", 100),
            duration_seconds=data.get("duration_seconds", 30),
            global_seed=data.get("global_seed", 42),
        )
