# SETVE Local Cluster Emulator (`deploy/emulator/`)

Emulates a distributed, multi-node storage load generation cluster entirely on local host infrastructure.

---

## Capabilities
1. **Multi-Node Topology Simulation**: Spawns multiple simulated cluster nodes with dedicated worker process pools.
2. **gRPC Barrier Synchronization**: Replicates distributed synchronization handshakes before unleashing concurrent storage I/O.
3. **Aggregated Cluster Telemetry**: Merges per-core metrics into unified HDR latency distributions and aggregate cluster bandwidth.

---

## Running the Cluster Emulator

```bash
# Run a 4-node, 8-core cluster at 10 Gbps for 3 seconds
python deploy/emulator/cluster_runner.py --nodes 4 --cores-per-node 2 --duration 3.0 --rate 10.0

# Run a large 16-node cluster at 20 Gbps
python deploy/emulator/cluster_runner.py --nodes 16 --cores-per-node 2 --duration 2.0 --rate 20.0
```
