#!/usr/bin/env python3
"""SETVE Environment & Directory Bootstrap Generator."""

from pathlib import Path
import sys

DIRECTORIES = [
    ".index",
    "docs/01-brd/data-plane",
    "docs/02-hld/compute-engine",
    "docs/03-adr",
    "docs/04-lld/memory",
    "scripts",
    "setve/adapters",
    "setve/payload",
    "setve/orchestrator",
    "setve/validation",
    "tests",
]

FILES = {
    "setve/__init__.py": '"""SETVE: Universal Simulation & Telemetry Validation Engine."""\n__version__ = "0.1.0"\n',
    "setve/py.typed": "",
    "setve/adapters/__init__.py": "",
    "setve/payload/__init__.py": "",
    "setve/orchestrator/__init__.py": "",
    "setve/validation/__init__.py": "",
    "tests/__init__.py": "",
    "docs/01-brd/data-plane/BRD-SETVE-001.md": """---
id: "BRD-SETVE-001"
title: "Universal High-Throughput Simulation & Telemetry Validation Engine (SETVE)"
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
owner: "@architecture-team"
last_validated_date: "2026-08-05"
---

# BRD-SETVE-001: Universal High-Throughput Simulation & Telemetry Validation Engine

## 1. Executive Summary
Provide continuous data generation and ingestion simulation at $\\ge 8\\text{ GB/s}$ sustained throughput.
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
  implements_brd: ["BRD-SETVE-001"]
  governed_by_adr: []
  parent_hld: null
  child_llds: []
code_references:
  - "setve/adapters/io_uring.py"
owner: "@architecture-team"
last_validated_date: "2026-08-05"
---

# ADR-0001: Use Linux io_uring for Zero-Copy Direct I/O

## Context
High-throughput storage simulation requires kernel-bypass or asynchronous queue submissions to avoid syscall overhead.
""",
}


def bootstrap() -> None:
    root = Path.cwd()
    print(f"Initializing SETVE workspace in: {root}")

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
