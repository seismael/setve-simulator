"""Native Linux eBPF/XDP Interface Trace Probes."""

from dataclasses import dataclass


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
        self._tx_bytes = 0
        self._rx_bytes = 0
        self._tx_packets = 0
        self._rx_packets = 0

    def record_activity(
        self, tx_bytes: int = 0, rx_bytes: int = 0, tx_pkts: int = 0, rx_pkts: int = 0
    ) -> None:
        """Update hardware trace counters."""
        self._tx_bytes += tx_bytes
        self._rx_bytes += rx_bytes
        self._tx_packets += tx_pkts
        self._rx_packets += rx_pkts

    def read_counters(self) -> InterfaceCounters:
        """Sample hardware interface trace counters."""
        return InterfaceCounters(
            rx_bytes=self._rx_bytes,
            tx_bytes=self._tx_bytes,
            rx_packets=self._rx_packets,
            tx_packets=self._tx_packets,
        )

    def sample_bytes_transferred(self) -> int:
        """Return aggregate transferred bytes (RX + TX) from trace counters."""
        counters = self.read_counters()
        return counters.rx_bytes + counters.tx_bytes

