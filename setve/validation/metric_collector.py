"""Sub-millisecond HDRHistogram Metric Collectors."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class MetricCollector:
    """Latency and throughput metric aggregator."""

    latencies_ns: List[int] = field(default_factory=list)

    def record_latency(self, latency_ns: int) -> None:
        """Record operation latency in nanoseconds."""
        self.latencies_ns.append(latency_ns)

    def p99_latency_ms(self) -> float:
        """Calculate p99 latency metric."""
        if not self.latencies_ns:
            return 0.0
        sorted_lat = sorted(self.latencies_ns)
        idx = int(len(sorted_lat) * 0.99)
        return sorted_lat[min(idx, len(sorted_lat) - 1)] / 1e6
