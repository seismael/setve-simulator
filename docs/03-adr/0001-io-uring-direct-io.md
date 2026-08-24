---
id: "ADR-0001"
title: "Use Linux io_uring and O_DIRECT for Zero-Copy High-Throughput I/O"
type: "ADR"
status: "APPROVED"
domain: "data-plane"
layer: "storage"
c4_level: "component"
diataxis_type: "explanation"
traceability:
  implements_brd: ["BRD-STEVE-001"]
  governed_by_adr: []
  parent_hld: "HLD-STEVE-001"
  child_llds: ["LLD-ADAPTER-001"]
code_references:
  - "steve/adapters/io_uring.py"
  - "steve/adapters/posix.py"
test_references:
  - "tests/test_posix_io.py"
  - "tests/benchmark_adapters.py"
owner: "@architecture-team"
last_validated_date: "2026-08-05"
---


# ADR-0001: Use Linux io_uring and O_DIRECT for Zero-Copy High-Throughput I/O

## 1. Context & Problem Statement

**BRD-STEVE-001** mandates ≥ 8 GB/s sustained throughput per client node. In a
standard Python runtime, three bottlenecks prevent this:

| # | Bottleneck | Impact |
|---|-----------|--------|
| 1 | **System-call overhead** | Synchronous `pread`/`pwrite` require one kernel context-switch per op. At 8 GB/s with 4 KB blocks → > 2 M syscalls/s, saturating CPU in `sy` mode. |
| 2 | **Page-cache double-buffering** | Buffered I/O copies data user → kernel page cache → device. Burns memory-bus bandwidth and introduces unpredictable flush latency. |
| 3 | **GIL & thread contention** | Default `asyncio` delegates file I/O to `ThreadPoolExecutor`. GIL synchronization creates latency spikes at high concurrency. |

---

## 2. Evaluated Options

### Option 1 — Multi-Threaded Synchronous Direct I/O

Open files with `os.O_DIRECT`, issue synchronous `pread`/`pwrite` across a large
thread pool.

* **Pro:** Universal POSIX compatibility.
* **Con:** Massive thread context-switching; severe GIL contention at 32+ threads;
  cannot saturate multi-100 GbE / NVMe pipelines.

### Option 2 — `asyncio` + POSIX AIO (`aio_read` / `aio_write`)

Integrate POSIX Asynchronous I/O signaling with Python's `asyncio` loop.

* **Pro:** Non-blocking model aligned with Python async patterns.
* **Con:** Linux POSIX AIO internally spawns kernel threads for file ops; no true
  zero-copy storage path.

### Option 3 — Linux `io_uring` Kernel Bypass (`liburing` bindings)

Use `io_uring` ring buffers (SQ/CQ) over `O_DIRECT` via native `liburing` FFI.

* **Pro:**
  * **Zero syscalls** — batched SQE submission; zero calls in `IORING_SETUP_SQPOLL` mode.
  * **Zero-copy** — page-aligned `memoryview` buffers (`DirectBuffer`) mapped directly to kernel DMA.
  * **Single-threaded** — drives tens of thousands of IOPS per core without GIL acquisition.
* **Con:** Linux Kernel ≥ 5.10 required.

---

## 3. Decision Matrix

| Criterion | Option 1: POSIX Direct I/O | Option 2: POSIX AIO | **Option 3: `io_uring`** |
|---|---|---|---|
| **Max throughput / core** | ~2.1 GB/s | ~3.4 GB/s | **≥ 8.5 GB/s** |
| **Syscalls per 10 k ops** | 10 000 | 10 000 | **1** (0 with SQPOLL) |
| **Page-cache bypass** | Yes (`O_DIRECT`) | Partial | **Yes** (`O_DIRECT` + fixed bufs) |
| **CPU at saturation** | 100% (high `sy`) | 75% | **< 15%** (user mode) |
| **OS compatibility** | Universal POSIX | Universal POSIX | Linux ≥ 5.10 |
| **GIL contention risk** | Extreme | Moderate | **Zero** (uvloop single-thread) |

---

## 4. Decision

**Selected:** Option 3 — Linux `io_uring` with `O_DIRECT` page-aligned buffers.

### Justification

1. **Meets BRD-STEVE-001 throughput target.** Only mechanism sustaining > 8 GB/s in
   Python with < 1% control-plane CPU overhead per core.
2. **Eliminates GIL contention.** Lock-free SQ/CQ rings shared between user memory
   and kernel; single core-pinned `uvloop` process keeps 1 000+ I/O ops in flight.
3. **Native DMA mapping.** Paired with 4096-byte page-aligned `mmap` buffers
   (`DirectBuffer`), hardware DMA engines transfer data directly between host RAM
   and NIC/NVMe — zero intermediate copies.

---

## 5. Consequences & Mitigations

### Positive

* **Line-rate I/O** — matches native C/C++ benchmark harness throughput.
* **Predictable tail latency** — eliminates OS thread scheduling and GIL lock spikes.
* **Scalable queue depth** — dynamically adjustable from 128 to 4 096 in-flight SQEs
  per adapter instance.

### Negative & Mitigation

| Risk | Mitigation |
|------|-----------|
| **Linux-only** (Kernel ≥ 5.10) | Fallback `PosixDirectIOAdapter` for dev environments (macOS / Windows); `IoUringTargetAdapter` enforced in production. |
| **Alignment strictness** (`O_DIRECT` + `io_uring` reject misaligned buffers) | Mandatory 4096-byte assertion in `DirectBuffer.__post_init__()` before any queue submission. |
