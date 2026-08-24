#!/usr/bin/env bash
set -euo pipefail

# 1. Update Linux System Packages & Install Build Tools
apt-get update -y
apt-get install -y \
    build-essential \
    clang \
    llvm \
    libbpf-dev \
    linux-tools-common \
    linux-tools-generic \
    linux-tools-$(uname -r) \
    liburing-dev \
    pkg-config \
    python3-pip \
    python3-dev \
    git \
    htop \
    numactl

# 2. Configure High-Performance Kernel Parameters (io_uring & HugePages)
cat <<'EOF' > /etc/sysctl.d/99-steve-performance.conf
# Enable unprivileged eBPF and io_uring
kernel.unprivileged_bpf_disabled=0
net.core.bpf_jit_enable=1

# Storage & Async I/O queue limits
fs.aio-max-nr=1048576
fs.file-max=2097152

# Increase network socket buffers for line-rate throughput
net.core.rmem_max=134217728
net.core.wmem_max=134217728
net.core.rmem_default=67108864
net.core.wmem_default=67108864
net.ipv4.tcp_rmem=4096 87380 134217728
net.ipv4.tcp_wmem=4096 65536 134217728

# Configure 2MB HugePages (8192 pages = 16GB RAM allocated)
vm.nr_hugepages=8192
vm.max_map_count=262144
EOF

sysctl --system

# 3. Configure Lockable Memory Limits for O_DIRECT & User-Space Buffers
cat <<'EOF' >> /etc/security/limits.conf
*    soft    memlock    unlimited
*    hard    memlock    unlimited
*    soft    nofile     1048576
*    hard    nofile     1048576
root soft    memlock    unlimited
root hard    memlock    unlimited
root soft    nofile     1048576
root hard    nofile     1048576
EOF

# 4. Install Docker & Enable User-Space Runtime Privileges
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
usermod -aG docker ubuntu

# 5. Verify io_uring Support in Kernel
if grep -q "CONFIG_IO_URING=y" /boot/config-$(uname -r); then
    echo "SUCCESS: Linux Kernel $(uname -r) supports native io_uring."
else
    echo "WARNING: Check kernel features for io_uring support."
fi

echo "STEVE Dev Sandbox initialization complete."
