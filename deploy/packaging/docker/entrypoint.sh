#!/bin/bash
set -e

# SETVE Containerized Runtime Entrypoint
echo "=================================================================="
echo "  SETVE CONTAINER RUNTIME: Initializing Execution Environment"
echo "=================================================================="

# Diagnostic check for kernel capabilities and NUMA availability
if command -v numactl >/dev/null 2>&1; then
    echo "[*] NUMA Topology detected:"
    numactl --hardware || true
fi

# Ensure scratch directory and shared memory directories exist
mkdir -p /data/scratch /dev/shm/setve

echo "[*] SETVE execution environment ready. Launching payload:"
echo "    -> Command: $@"
echo "=================================================================="

exec "$@"
