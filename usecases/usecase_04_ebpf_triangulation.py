"""Use Case 04: Out-of-Band eBPF Telemetry Triangulation & Ground-Truth Verification.

Demonstrates triangulating application-level client telemetry metrics against
out-of-band kernel/hardware interface counters to mathematically verify data-plane
accuracy and detect metric skew (tolerance <= 0.1%).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure setve package is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from setve.validation.ebpf_probe import EBPFProbe  # noqa: E402
from setve.validation.evaluator import TelemetryEvaluator  # noqa: E402


def run_ebpf_triangulation(
    simulated_transfer_mb: int = 1024,
    skew_drift_bytes: int = 0,
    tolerance_percent: float = 0.1,
    interface_name: str = "eth0",
    mtu_bytes: int = 1500,
) -> int:
    """Evaluate telemetry skew between client and kernel counters."""
    print("=" * 80)
    print("  SETVE USE CASE 04: eBPF Ground-Truth Telemetry Triangulation")
    print("=" * 80)

    client_bytes = simulated_transfer_mb * 1024 * 1024
    probe_bytes = client_bytes + skew_drift_bytes
    expected_pkts = max(1, client_bytes // mtu_bytes)
    probe_pkts = max(1, probe_bytes // mtu_bytes)

    print(f"[*] Target Interface:       {interface_name} (MTU: {mtu_bytes}B)")
    print(f"[*] Client Reported Size:   {simulated_transfer_mb:,} MB ({client_bytes:,} bytes)")
    print(f"[*] Client Estimated Pkts:  {expected_pkts:,} frames")
    print(f"[*] Skew Drift Injected:    {skew_drift_bytes:,} bytes")
    print(f"[*] SLA Permitted Tolerance: <= {tolerance_percent}%\n")

    probe = EBPFProbe(interface=interface_name)
    probe.record_activity(tx_bytes=probe_bytes, rx_bytes=0, tx_pkts=probe_pkts)

    evaluator = TelemetryEvaluator(skew_threshold_percent=tolerance_percent)
    divergence = evaluator.evaluate(
        client_bytes=client_bytes,
        probe_bytes=probe.sample_bytes_transferred(),
    )

    status_str = "VALID (PASS <= 0.1% SLA)" if divergence.is_valid else "FAIL (SKEW DETECTED)"
    print("+--------------------------------------------------------------------------------+")
    print("| TELEMETRY TRIANGULATION & GROUND-TRUTH VERIFICATION REPORT                     |")
    print("+--------------------------------------------------------------------------------+")
    print(
        f"| Client Reported Data:    {divergence.client_bytes:>16,} bytes "
        f"({divergence.client_bytes / 1e9:.3f} GB)            |"
    )
    print(
        f"| eBPF Hardware Counter:   {divergence.probe_bytes:>16,} bytes "
        f"({divergence.probe_bytes / 1e9:.3f} GB)            |"
    )
    delta_str = f"{divergence.delta_bytes:,} bytes"
    print(f"| Delta Discrepancy:       {delta_str:>16}                                 |")
    skew_str = f"{divergence.divergence_percent:.4f}%"
    print(f"| Measured Metric Skew:    {skew_str:>16}                                 |")
    print(f"| Physical Egress Packets: {probe_pkts:>16,} frames                                |")
    print(f"| Triangulation Status:    {status_str:>26}                      |")
    print("+--------------------------------------------------------------------------------+")

    if not divergence.is_valid:
        print("\n[!] DIAGNOSTIC ADVISORY: Telemetry divergence exceeds threshold!")
        if divergence.delta_bytes > 0:
            print("    -> Hardware probe observed MORE bytes than client reported.")
            print(
                "    -> Root Cause: Kernel TCP retransmissions, TLS encapsulation,\n"
                "       or unmonitored background tenant activity sharing the physical NIC."
            )
            print("    -> Recommended Action: Inspect `ethtool -S <iface> | grep retrans` and")
            print("       verify cgroup network bandwidth isolation rules.")
        else:
            print("    -> Hardware probe observed FEWER bytes than client reported.")
            print(
                "    -> Root Cause: Client socket write buffer inflation, un-flushed send queues,"
            )
            print("       or silent frame drops prior to physical NIC ring descriptor enqueue.")
            print(
                "    -> Recommended Action: Enforce `TCP_NODELAY`, audit ring buffer overruns via"
            )
            print("       `ethtool -g <iface>`, and tune `net.core.wmem_max`.")
    else:
        print("\n[+] Telemetry integrity verified: Zero unaccounted packet drops or metric drift.")

    print()
    return 0 if divergence.is_valid else 1


def main() -> int:
    """Parse CLI options and execute triangulation evaluation."""
    parser = argparse.ArgumentParser(description="SETVE Use Case 04: eBPF Telemetry Triangulator")
    parser.add_argument(
        "--transfer-mb",
        type=int,
        default=1024,
        help="Simulated transfer in MB (default: 1024)",
    )
    parser.add_argument(
        "--drift-bytes",
        type=int,
        default=0,
        help="Injected metric drift in bytes (default: 0)",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.1,
        help="Max allowable divergence percent (default: 0.1)",
    )
    parser.add_argument(
        "--interface",
        type=str,
        default="eth0",
        help="Hardware network/storage interface name (default: eth0)",
    )
    parser.add_argument(
        "--mtu",
        type=int,
        default=1500,
        help="Network interface MTU size in bytes (default: 1500)",
    )

    args = parser.parse_args()
    return run_ebpf_triangulation(
        simulated_transfer_mb=args.transfer_mb,
        skew_drift_bytes=args.drift_bytes,
        tolerance_percent=args.tolerance,
        interface_name=args.interface,
        mtu_bytes=args.mtu,
    )


if __name__ == "__main__":
    sys.exit(main())
