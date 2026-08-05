"""Telemetry Triangulation & Divergence Calculator."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DivergenceResult:
    """Telemetry accuracy calculation result."""

    client_bytes: int
    probe_bytes: int
    delta_bytes: int
    divergence_percent: float
    is_valid: bool


class TelemetryEvaluator:
    """Out-of-band telemetry cross-evaluator computing metric skew."""

    def evaluate(self, client_bytes: int, probe_bytes: int) -> DivergenceResult:
        """Calculate divergence between client metrics and kernel ground truth."""
        delta = abs(client_bytes - probe_bytes)
        denom = max(probe_bytes, 1)
        divergence_pct = (delta / denom) * 100.0
        is_valid = divergence_pct <= 0.1  # Target <= 0.1% divergence

        return DivergenceResult(
            client_bytes=client_bytes,
            probe_bytes=probe_bytes,
            delta_bytes=delta,
            divergence_percent=divergence_pct,
            is_valid=is_valid,
        )
