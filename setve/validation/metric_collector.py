"""Sub-millisecond HDRHistogram Metric Collectors."""

from dataclasses import dataclass, field


@dataclass(slots=True)
class MetricCollector:
    """Zero-allocation latency and throughput HDR histogram aggregator."""

    # 64 logarithmic buckets covering 1 ns up to ~18.4 seconds (2^64 ns)
    _buckets: list[int] = field(default_factory=lambda: [0] * 64)
    _total_ops: int = 0
    _total_bytes: int = 0
    _min_latency_ns: int = 0xFFFFFFFFFFFFFFFF
    _max_latency_ns: int = 0

    def record_latency(self, latency_ns: int) -> None:
        """Record operation latency in nanoseconds with zero heap allocations (O(1))."""
        idx = latency_ns.bit_length()
        if idx >= 64:
            idx = 63

        self._buckets[idx] += 1
        self._total_ops += 1

        if latency_ns < self._min_latency_ns:
            self._min_latency_ns = latency_ns
        if latency_ns > self._max_latency_ns:
            self._max_latency_ns = latency_ns

    def record_bytes(self, byte_count: int) -> None:
        """Record transferred byte count."""
        self._total_bytes += byte_count

    @property
    def total_ops(self) -> int:
        """Return total operations recorded."""
        return self._total_ops

    @property
    def total_bytes(self) -> int:
        """Return total bytes transferred."""
        return self._total_bytes

    def percentile_ms(self, p: float) -> float:
        """Calculate percentile latency metric in milliseconds (p in [0.0, 1.0])."""
        if self._total_ops == 0:
            return 0.0

        target_count = int(self._total_ops * min(max(p, 0.0), 1.0))
        accumulated = 0

        for bucket_idx, count in enumerate(self._buckets):
            accumulated += count
            if accumulated >= target_count:
                # Estimate representative latency for bucket (upper bound approximation)
                upper_bound_ns = 1 << bucket_idx if bucket_idx > 0 else 1
                return upper_bound_ns / 1e6

        return self._max_latency_ns / 1e6

    def p50_latency_ms(self) -> float:
        """Calculate p50 (median) latency metric."""
        return self.percentile_ms(0.50)

    def p90_latency_ms(self) -> float:
        """Calculate p90 latency metric."""
        return self.percentile_ms(0.90)

    def p99_latency_ms(self) -> float:
        """Calculate p99 latency metric."""
        return self.percentile_ms(0.99)

    def p999_latency_ms(self) -> float:
        """Calculate p99.9 latency metric."""
        return self.percentile_ms(0.999)

    def throughput_gbps(self, duration_sec: float) -> float:
        """Calculate aggregate throughput in Gigabits per second (Gbps)."""
        if duration_sec <= 0:
            return 0.0
        return (self._total_bytes * 8) / (duration_sec * 1e9)

    def throughput_bytes_per_sec(self, duration_sec: float) -> float:
        """Calculate aggregate throughput in Bytes per second."""
        if duration_sec <= 0:
            return 0.0
        return self._total_bytes / duration_sec

    def reset(self) -> None:
        """Reset all histogram metrics."""
        for i in range(64):
            self._buckets[i] = 0
        self._total_ops = 0
        self._total_bytes = 0
        self._min_latency_ns = 0xFFFFFFFFFFFFFFFF
        self._max_latency_ns = 0
