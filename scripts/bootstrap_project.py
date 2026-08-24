#!/usr/bin/env python3
"""STEVE Environment & Directory Bootstrap Generator."""

from pathlib import Path

DIRECTORIES = [
    ".index",
    "docs/01-brd/data-plane",
    "docs/02-hld/compute-engine",
    "docs/03-adr",
    "docs/04-lld/memory",
    "scripts",
    "steve/adapters",
    "steve/payload",
    "steve/orchestrator",
    "steve/validation",
    "tests",
]

FILES = {
    "steve/__init__.py": (
        '"""STEVE: Storage, Telemetry, Engine, Verification, and Evaluation."""\n'
        '__version__ = "0.2.0"\n'
    ),
    "steve/py.typed": "",
    "steve/adapters/__init__.py": "",
    "steve/payload/__init__.py": "",
    "steve/orchestrator/__init__.py": "",
    "steve/validation/__init__.py": "",
    "tests/__init__.py": "",
    "docs/01-brd/data-plane/BRD-STEVE-001.md": """---
id: "BRD-STEVE-001"
title: "Storage, Telemetry, Engine, Verification, and Evaluation (STEVE)"
type: "BRD"
status: "APPROVED"
domain: "data-plane"
layer: "compute-engine"
c4_level: "context"
diataxis_type: "explanation"
traceability:
  implements_brd: []
  governed_by_adr: []
  parent_hld: null
  child_llds: []
code_references: []
test_references: []
owner: "@architecture-team"
last_validated_date: "2026-08-05"
---

# BRD-STEVE-001: Storage, Telemetry, Engine, Verification, and Evaluation

## 1. Executive Summary
Provide continuous data generation and ingestion simulation at $\\ge 8\\text{ GB/s}$
sustained throughput.
""",
    "docs/03-adr/0001-io-uring-direct-io.md": """---
id: "ADR-0001"
title: "Use Linux io_uring for Zero-Copy Direct I/O"
type: "ADR"
status: "APPROVED"
domain: "data-plane"
layer: "storage"
c4_level: "component"
diataxis_type: "explanation"
traceability:
  implements_brd: ["BRD-STEVE-001"]
  governed_by_adr: []
  parent_hld: null
  child_llds: []
code_references:
  - "steve/adapters/io_uring.py"
test_references:
  - "tests/test_posix_io.py"
owner: "@architecture-team"
last_validated_date: "2026-08-05"
---

# ADR-0001: Use Linux io_uring for Zero-Copy Direct I/O

## Context
High-throughput storage simulation requires kernel-bypass or asynchronous queue submissions
to avoid syscall overhead.
""",
}


def bootstrap() -> None:
    root = Path.cwd()
    print(f"Initializing STEVE workspace in: {root}")

    for folder in DIRECTORIES:
        p = root / folder
        p.mkdir(parents=True, exist_ok=True)
        print(f"  [+] Directory created: {folder}")

    for file_path, content in FILES.items():
        p = root / file_path
        if not p.exists():
            p.write_text(content.strip() + "\n", encoding="utf-8")
            print(f"  [+] File created: {file_path}")

    print("\nBootstrap complete! Run 'make install' to set up Python environment.")


if __name__ == "__main__":
    bootstrap()
