"""Tests for MetricCollector HDR Histogram aggregation and throughput metrics."""

from setve.validation.metric_collector import MetricCollector


def test_metric_collector_empty_state() -> None:
    """Verify empty collector returns 0.0 for percentiles and throughput."""
    collector = MetricCollector()
    assert collector.total_ops == 0
    assert collector.total_bytes == 0
    assert collector.p50_latency_ms() == 0.0
    assert collector.p90_latency_ms() == 0.0
    assert collector.p99_latency_ms() == 0.0
    assert collector.throughput_gbps(10.0) == 0.0


def test_metric_collector_latency_percentiles() -> None:
    """Verify logarithmic histogram calculates expected percentile bounds."""
    collector = MetricCollector()

    # Record 100 operations with known latencies:
    # 90 ops at 1,000,000 ns (1 ms), 10 ops at 100,000,000 ns (100 ms)
    for _ in range(90):
        collector.record_latency(1_000_000)
    for _ in range(10):
        collector.record_latency(100_000_000)

    assert collector.total_ops == 100

    # p50 should be ~1 ms range
    p50 = collector.p50_latency_ms()
    assert 0.5 <= p50 <= 2.5

    # p99 should be in the higher bucket range (>= 60 ms)
    p99 = collector.p99_latency_ms()
    assert p99 >= 50.0


def test_metric_collector_throughput() -> None:
    """Verify throughput calculations in Gbps and Bytes/sec."""
    collector = MetricCollector()

    # 1 GB in 1 second = 8 Gbps
    one_gb = 1024**3
    collector.record_bytes(one_gb)

    gbps = collector.throughput_gbps(1.0)
    assert 8.58 <= gbps <= 8.60

    bps = collector.throughput_bytes_per_sec(1.0)
    assert bps == one_gb


def test_metric_collector_reset() -> None:
    """Verify collector reset clears all state."""
    collector = MetricCollector()
    collector.record_latency(5000)
    collector.record_bytes(1024)
    assert collector.total_ops == 1
    assert collector.total_bytes == 1024

    collector.reset()
    assert collector.total_ops == 0
    assert collector.total_bytes == 0
    assert collector.p99_latency_ms() == 0.0
