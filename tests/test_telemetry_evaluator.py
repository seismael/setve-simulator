"""Tests for TelemetryEvaluator and divergence calculation."""

from setve.validation.evaluator import TelemetryEvaluator


def test_telemetry_evaluator_valid() -> None:
    """Verify divergence <= 0.1% passes fidelity check."""
    evaluator = TelemetryEvaluator()

    # 10,000,000 bytes vs 10,005,000 bytes -> 0.05% divergence <= 0.1%
    result = evaluator.evaluate(client_bytes=10_005_000, probe_bytes=10_000_000)

    assert result.delta_bytes == 5000
    assert abs(result.divergence_percent - 0.05) < 1e-4
    assert result.is_valid is True


def test_telemetry_evaluator_skew_alarm() -> None:
    """Verify divergence > 0.1% fails fidelity check."""
    evaluator = TelemetryEvaluator()

    # 10,000,000 bytes vs 10,100,000 bytes -> 1.0% divergence > 0.1%
    result = evaluator.evaluate(client_bytes=10_100_000, probe_bytes=10_000_000)

    assert result.delta_bytes == 100_000
    assert abs(result.divergence_percent - 1.0) < 1e-4
    assert result.is_valid is False


def test_telemetry_evaluator_zero_bytes() -> None:
    """Verify zero bytes handled safely without division by zero."""
    evaluator = TelemetryEvaluator()
    result = evaluator.evaluate(client_bytes=0, probe_bytes=0)
    assert result.delta_bytes == 0
    assert result.divergence_percent == 0.0
    assert result.is_valid is True
