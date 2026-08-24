"""Extended Unit Tests for MetricCollector HDR Histogram Boundaries and Percentiles."""

from steve.validation.metric_collector import MetricCollector


def test_metric_collector_extreme_ranges() -> None:
    """Verify MetricCollector accuracy across extreme nanosecond latency ranges."""
    collector = MetricCollector()

    # Record 990 operations at 100 microseconds
    for _ in range(990):
        collector.record_latency(100_000)

    # Record 8 operations at 10 milliseconds
    for _ in range(8):
        collector.record_latency(10_000_000)

    # Record 2 extreme outlier operations at 2 seconds
    collector.record_latency(2_000_000_000)  # 2 s
    collector.record_latency(2_000_000_000)  # 2 s
    collector.record_bytes(1048576)

    assert collector.total_ops == 1000
    assert collector.total_bytes == 1048576

    # Percentiles must be monotonically non-decreasing: p50 <= p90 <= p99 <= p99.9 <= max
    p50 = collector.p50_latency_ms()
    p90 = collector.p90_latency_ms()
    p99 = collector.p99_latency_ms()
    p999 = collector.p999_latency_ms()

    assert p50 <= p90
    assert p90 <= p99
    assert p99 <= p999
    assert p999 >= 1000.0  # 2-second tail is captured at p99.9 in 1000 ops (bucket 31 >= 2147 ms)


def test_metric_collector_reset_and_zero_state() -> None:
    """Verify MetricCollector behaves correctly when empty and after calling reset()."""
    collector = MetricCollector()
    assert collector.total_ops == 0
    assert collector.total_bytes == 0
    assert collector.p50_latency_ms() == 0.0
    assert collector.p90_latency_ms() == 0.0
    assert collector.p99_latency_ms() == 0.0
    assert collector.p999_latency_ms() == 0.0
    assert collector.throughput_gbps(1.0) == 0.0
    assert collector.throughput_gbps(0.0) == 0.0

    # Record metrics
    collector.record_latency(250_000)
    collector.record_bytes(4096)
    assert collector.total_ops == 1
    assert collector.total_bytes == 4096

    # Reset
    collector.reset()
    assert collector.total_ops == 0
    assert collector.total_bytes == 0
    assert collector.p50_latency_ms() == 0.0
    assert collector.throughput_gbps(1.0) == 0.0


def test_metric_collector_bucket_saturation() -> None:
    """Verify that latency values exceeding maximum bucket range saturate into the top bucket."""
    collector = MetricCollector()
    # Record an extreme outlier: 1,000,000,000,000,000,000 ns
    collector.record_latency(10**18)
    assert collector.total_ops == 1
    assert collector.p99_latency_ms() > 0.0
