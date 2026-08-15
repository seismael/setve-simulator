#!/bin/bash
set -e

echo "=================================================================="
echo "  SETVE: Universal Simulation & Telemetry Validation Engine"
echo "  Container Runtime Initializing..."
echo "=================================================================="

# Check CPU core availability
if command -v nproc > /dev/null 2>&1; then
    CORES=$(nproc)
    echo "[*] Detected $CORES Physical/Virtual CPU cores in container namespace"
fi

# Ensure shared memory mount or local scratch directory is ready
mkdir -p /data/scratch
export SETVE_SCRATCH_DIR=/data/scratch

echo "[*] Storage mount /data ready"
echo "[*] Executing workload command: $@"

exec "$@"
