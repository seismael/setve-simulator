# SETVE Local Multi-Node Distributed Cluster Emulation

The **Local Cluster Emulator** simulates a distributed multi-node storage generation cluster on a single workstation or server without requiring cloud VMs or physical multi-server hardware.

---

## Capabilities Tested
- **Deterministic Shard Boundary Partitioning:** Splits target throughput and address space using SplitMix64 across virtual nodes (`node-00` to `node-N`).
- **Cluster Barrier Handshakes:** Simulates distributed barrier synchronization via [ClusterSyncServicer](file:///c:/dev/projects/setve-simulator/setve/orchestrator/sync.py).
- **Multi-Node IPC Telemetry Aggregation:** Gathers per-node and per-core telemetry metrics into unified cluster summaries.

---

## CLI Usage

```bash
# Run a 4-node, 8-core cluster simulation for 3 seconds targeting 10 Gbps
python deployments/local_cluster/cluster_runner.py --nodes 4 --cores-per-node 2 --duration 3.0 --rate 10.0

# Run a high-density 16-node, 32-core cluster simulation
python deployments/local_cluster/cluster_runner.py --nodes 16 --cores-per-node 2 --duration 2.0 --rate 20.0
```
