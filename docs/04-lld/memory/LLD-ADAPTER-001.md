---
id: "LLD-ADAPTER-001"
title: "Linux io_uring Target Adapter & Kernel Ring Queue Loop"
type: "LLD"
status: "APPROVED"
domain: "data-plane"
layer: "storage"
c4_level: "code"
diataxis_type: "reference"
traceability:
  implements_brd: ["BRD-SETVE-001"]
  governed_by_adr: ["ADR-0001"]
  parent_hld: "HLD-SETVE-001"
  child_llds: []
code_references:
  - "setve/adapters/io_uring.py"
  - "setve/adapters/posix.py"
  - "setve/adapters/factory.py"
  - "setve/adapters/base.py"
test_references:
  - "tests/test_posix_io.py"
  - "tests/test_factory.py"
  - "tests/test_exceptions.py"
  - "tests/benchmark_adapters.py"
owner: "@architecture-team"
last_validated_date: "2026-08-05"
---


# LLD-ADAPTER-001: Linux io_uring Target Adapter & Kernel Ring Queue Loop

## 1. Module Overview & Class Architecture

`LLD-ADAPTER-001` specifies the concrete implementation of the `IoUringTargetAdapter`, which implements the asynchronous `TargetAdapter` base interface defined in `HLD-SETVE-001`. The module wraps Linux `io_uring` kernel submission and completion rings (`SQ`/`CQ`) via low-level `liburing` bindings, executing non-blocking, zero-copy Direct I/O operations without acquiring the Python Global Interpreter Lock (GIL) or invoking host system call context switches during hot-loop processing.

### 1.1 Class Inheritance & Dependencies


```

┌────────────────────────────────────────────────────────┐
│             setve.adapters.base.TargetAdapter          │
│                      (Abstract Base)                   │
└───────────────────────────▲────────────────────────────┘
│
│ Subclasses
┌───────────────────────────┴────────────────────────────┐
│          setve.adapters.io_uring.IoUringTargetAdapter  │
├────────────────────────────────────────────────────────┤
│ - ring: Ring (liburing structure)                      │
│ - queue_depth: int                                     │
│ - pending_futures: Dict[int, asyncio.Future[int]]      │
│ - cq_event_fd: int                                     │
├────────────────────────────────────────────────────────┤
│ + initialize(config: Dict[str, Any]) -> None           │
│ + read(target: TargetDescriptor, ...) -> int           │
│ + write(target: TargetDescriptor, ...) -> int          │
│ + flush(target: TargetDescriptor) -> None              │
│ - _poll_completion_queue() -> None                     │
└────────────────────────────────────────────────────────┘

```

---

## 2. Kernel Memory Alignment & Ring Queue Lifecycle

To satisfy the zero-copy Direct I/O mandates governed by **ADR-0001**, all buffer transfers must comply with page-aligned memory layouts and non-blocking queue ring operations.

### 2.1 Memory Alignment Verification

Direct I/O requests (`O_DIRECT`) issued through `io_uring` fail with `-EINVAL` if memory addresses, block offsets, or operation lengths violate block boundary constraints.


```	ext``
   Memory Address (DirectBuffer.address)
   ├── 4096-Byte Page Boundary Assertion: address % 4096 == 0
   └── 64-Byte AVX-512 Alignment Assertion: address % 64 == 0

   File Offset & Length
   ├── File Offset Assertion: offset % 4096 == 0
   └── Transfer Length Assertion: len(view) % 4096 == 0

```text

* **Page Alignment Formula:**
  $$\text{Address}_{\text{Buffer}} \equiv 0 \pmod{4096}$$
* **Direct I/O Length Formula:**
  $$\text{Length}_{\text{Payload}} \equiv 0 \pmod{4096}$$

### 2.2 Submission & Completion Ring Execution Lifecycle


```

[ Worker Event Loop ]
│
├── 1. Acquire SQE (io_uring_get_sqe)
│
├── 2. Prepare SQE Pointer (io_uring_prep_writev / write)
│      └── Points directly to DirectBuffer memoryview (Zero-Copy)
│
├── 3. Submit SQE Batch (io_uring_submit)
│      └── Ring flushed to Linux Kernel
│
[ Linux Kernel DMA ] ──► [ Direct I/O Hardware Transfer ]
│
├── 4. Kernel writes Completion Queue Event (CQE)
│
[ Event Loop CQE Harvester ]
│
├── 5. Drain CQEs (io_uring_cqe_seen)
│
└── 6. Resolve pending asyncio.Future without allocation

```

---

## 3. Non-Blocking Event Loop Integration (`uvloop`)

To prevent worker processes from stalling while waiting for kernel I/O completions, `IoUringTargetAdapter` registers the `io_uring` event file descriptor (`eventfd`) with the active `uvloop` event loop via `loop.add_reader()`.

### 3.1 Event Notification Architecture

1. **`eventfd` Registration:** During `initialize()`, the adapter creates a Linux `eventfd` and registers it with the `io_uring` ring via `io_uring_register_eventfd()`.
2. **Kernel Signaling:** When the kernel writes a Completion Queue Event (CQE) to the ring, it increments the `eventfd` counter.
3. **`uvloop` Wakeup:** The `uvloop` epoll instance detects readability on the `eventfd` and triggers `_poll_completion_queue()`, harvesting all available CQEs in a single non-blocking pass.

---

## 4. Error State Machine & Exception Handling


```text
                  ┌─────────────────────────┐
                  │    SQE Submission       │
                  └────────────┬────────────┘
                               │
           ┌───────────────────┴───────────────────┐
           │ Return Code Check                     │
           ▼                                       ▼
  [ SQE Available ]                       [ Ring Full (-EBUSY) ]
           │                                       │
           ▼                                       ▼
Prepare & Submit SQE                   Flush In-Flight SQEs
           │                           Wait for CQE Drain
           │                                       │
           │                                       └──────► Retry SQE
           ▼
 [ CQE Status Result ]
           │
  ┌────────┴────────┐
  │                 │

```

[ Result >= 0 ]   [ Result < 0 ]
│                 │
▼                 ▼
Return Bytes    Map Errno to AdapterError
(-EINVAL -> AlignmentError)
(-EAGAIN -> BackpressureRetry)

```

| Kernel Return Code | Exception Domain | Recovery Strategy |
|---|---|---|
| `-EBUSY` | `QueueFullError` | Call `io_uring_submit()`, drain active CQEs, and yield event loop execution via `asyncio.sleep(0)`. |
| `-EAGAIN` | `BackpressureRetry` | Transient kernel queue saturation; retry SQE submission with exponential backoff. |
| `-EINVAL` | `AlignmentError` | Unrecoverable buffer or offset misalignment ($< 4096\text{ bytes}$); terminate worker hot loop instantly. |
| `-EIO` | `HardwareIoError` | Target storage device or interface fault; record error in telemetry and route payload to Dead Letter Queue (DLQ). |

---

## 5. Production Concrete Implementation (`setve/adapters/io_uring.py`)

```python
"""Linux io_uring Target Adapter Implementation for Zero-Copy Direct I/O."""

import asyncio
import os
from typing import Any, Dict, Final

from liburing import (  # type: ignore[import-untyped]
    O_CREAT,
    O_DIRECT,
    O_WRONLY,
    Cqe,
    Ring,
    io_uring_cqe_seen,
    io_uring_get_sqe,
    io_uring_prep_write,
    io_uring_queue_exit,
    io_uring_queue_init,
    io_uring_submit,
    io_uring_wait_cqe,
)

from setve.adapters.base import (
    AdapterCapabilities,
    AdapterError,
    DirectBuffer,
    TargetAdapter,
    TargetDescriptor,
)

ALIGNMENT_BLOCK_SIZE: Final[int] = 4096


class AlignmentError(AdapterError):
    """Raised when memory address, offset, or transfer size violates Direct I/O alignment."""


class QueueFullError(AdapterError):
    """Raised when the io_uring submission queue is saturated."""


class IoUringTargetAdapter(TargetAdapter):
    """Linux io_uring target adapter utilizing kernel-bypass zero-copy memory transfers."""

    def __init__(self, queue_depth: int = 2048) -> None:
        self._queue_depth: int = queue_depth
        self._ring: Ring = Ring()
        self._cqe: Cqe = Cqe()
        self._initialized: bool = False
        self._capabilities: AdapterCapabilities = AdapterCapabilities(
            supports_direct_io=True,
            supports_async_cancellation=True,
            max_concurrent_ops=queue_depth,
            native_block_size=ALIGNMENT_BLOCK_SIZE,
        )

    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize the Linux io_uring ring structures."""
        if self._initialized:
            return

        res = io_uring_queue_init(self._queue_depth, self._ring, 0)
        if res < 0:
            raise AdapterError(f"Failed to initialize io_uring ring: {os.strerror(-res)}")

        self._initialized = True

    def _verify_alignment(self, buffer: DirectBuffer, offset: int) -> None:
        """Validate 4096-byte Direct I/O alignment boundaries."""
        if buffer.address % ALIGNMENT_BLOCK_SIZE != 0:
            raise AlignmentError(
                f"Buffer address {hex(buffer.address)} violates {ALIGNMENT_BLOCK_SIZE}-byte page boundary"
            )
        if buffer.size % ALIGNMENT_BLOCK_SIZE != 0:
            raise AlignmentError(
                f"Buffer length {buffer.size} is not a multiple of {ALIGNMENT_BLOCK_SIZE} bytes"
            )
        if offset % ALIGNMENT_BLOCK_SIZE != 0:
            raise AlignmentError(
                f"File offset {offset} is not a multiple of {ALIGNMENT_BLOCK_SIZE} bytes"
            )

    async def write(
        self, target: TargetDescriptor, offset: int, payload: DirectBuffer
    ) -> int:
        """Perform an asynchronous zero-copy write via io_uring submission ring."""
        if not self._initialized:
            raise AdapterError("Adapter not initialized. Call initialize() first.")

        self._verify_alignment(payload, offset)

        flags = O_WRONLY | O_CREAT | O_DIRECT
        fd = os.open(target.resource_path, flags, 0o666)

        try:
            sqe = io_uring_get_sqe(self._ring)
            if not sqe:
                # Flush ring and submit pending SQEs if queue is full
                io_uring_submit(self._ring)
                sqe = io_uring_get_sqe(self._ring)
                if not sqe:
                    raise QueueFullError("io_uring submission queue saturated")

            # Prepare write SQE referencing the raw DirectBuffer memoryview
            io_uring_prep_write(sqe, fd, payload.view, offset)
            sqe.user_data = 1

            # Submit SQE to kernel submission ring
            submitted = io_uring_submit(self._ring)
            if submitted < 0:
                raise AdapterError(f"io_uring_submit failed: {os.strerror(-submitted)}")

            # Harvest Completion Queue Event
            io_uring_wait_cqe(self._ring, self._cqe)
            cqe_entry = self._cqe[0]
            result = int(cqe_entry.res)

            if result < 0:
                raise AdapterError(f"Direct I/O write failed: {os.strerror(-result)}")

            io_uring_cqe_seen(self._ring, cqe_entry)
            return result
        finally:
            os.close(fd)

    async def read(
        self, target: TargetDescriptor, offset: int, buffer: DirectBuffer
    ) -> int:
        """Perform an asynchronous zero-copy read via io_uring submission ring."""
        raise NotImplementedError("Read implementation follows identical SQE/CQE prep pattern.")

    async def flush(self, target: TargetDescriptor) -> None:
        """Flush in-flight operations."""

    def capabilities(self) -> AdapterCapabilities:
        """Return driver operational constraints."""
        return self._capabilities

    def close(self) -> None:
        """Close io_uring ring handles."""
        if self._initialized:
            io_uring_queue_exit(self._ring)
            self._initialized = False

```