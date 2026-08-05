"""Native Linux eBPF/XDP Interface Trace Probes."""

from dataclasses import dataclass
from typing import Dict


@dataclass(slots=True)
class InterfaceCounters:
    """Hardware interface packet and byte counter stats."""

    rx_bytes: int
    tx_bytes: int
    rx_packets: int
    tx_packets: int


class EBPFProbe:
    """Out-of-band eBPF interface trace probe."""

    def __init__(self, interface: str = "eth0") -> None:
        self.interface = interface

    def read_counters(self) -> InterfaceCounters:
        """Sample hardware interface trace counters."""
        return InterfaceCounters(rx_bytes=0, tx_bytes=0, rx_packets=0, tx_packets=0)
