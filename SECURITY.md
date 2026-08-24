# Security Policy

## Supported Versions

| Version | Supported          |
| :--- | :--- |
| `0.2.x` | :white_check_mark: |
| `0.1.x` | :white_check_mark: |
| `< 0.1.0` | :x: |

---

## Privileged Operations & Isolation Boundaries

STEVE is engineered for raw, high-throughput data-plane generation and utilizes low-level operating system primitives:

1. **Direct I/O (`O_DIRECT`):** Requires physical block alignment and may require write access to raw block devices (e.g. `/dev/nvme0n1`). Ensure target paths do not overlap with operating system root or boot partitions.
2. **CPU Affinity Pinning (`os.sched_setaffinity`):** Modifies CPU core masks for worker processes. On Linux, this requires standard process permissions or container `cpuset` delegations.
3. **Kernel Bypass (`io_uring`):** Uses Linux kernel `io_uring` ring queues. Verify host kernel version ($\ge 5.10$) and container seccomp profiles allow `io_uring_setup` and `io_uring_enter` syscalls.

---

## Reporting a Vulnerability

If you discover a security vulnerability within STEVE:

1. **Do NOT open a public issue.**
2. Report the vulnerability privately via GitHub Security Advisories or by emailing the architecture security team.
3. Include detailed steps to reproduce the vulnerability, impacted subsystems, and host environment specifications.
4. The security response team will acknowledge receipt within 48 hours and coordinate a patch and CVE disclosure timeline.
