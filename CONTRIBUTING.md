# Contributing to STEVE

Thank you for your interest in contributing to the **Storage, Telemetry, Engine, Verification, and Evaluation (STEVE)**!

STEVE is an open-source, high-performance load generation and telemetry verification framework built with strict Domain-Driven Design (DDD), Gang of Four (GoF) design patterns, and zero-allocation data-plane hot loops.

---

## 1. Code of Conduct

All contributors and maintainers are expected to adhere to our [Code of Conduct](CODE_OF_CONDUCT.md). Please read it before participating.

---

## 2. Architectural Guardrails & Non-Negotiables

When developing or modifying STEVE components, you **must** adhere to these core architectural constraints:

1. **Zero Allocations in Hot Paths:**
   - No heap allocations (`dict`, `list`, class instantiation, string concatenations) inside active read/write loops or payload mutation passes.
   - Slices must use pre-allocated, page-aligned `mmap` buffers and Python native `memoryview` objects.

2. **Core Isolation & Concurrency:**
   - Do NOT use standard `threading` for compute or I/O hot paths due to Global Interpreter Lock (GIL) contention.
   - Use `multiprocessing` with physical core binding (`os.sched_setaffinity`). Each worker process maintains an isolated event loop and `io_uring` ring instance.

3. **Hardware Alignment Verification:**
   - Direct I/O (`O_DIRECT`) kernel requests must satisfy $4096\text{-byte}$ alignment for direct buffers and offsets, and $64\text{-byte}$ alignment for AVX-512 SIMD vector operations.

4. **Dual-Indexed Documentation & DAG Traceability:**
   - All code changes must link to active LLD/HLD/ADR documents in `docs/` via YAML frontmatter `code_references:` and `test_references:`.
   - Run `python scripts/validate_docs.py` and `python scripts/build_doc_graph.py` before submitting a PR.

---

## 3. Getting Started & Development Setup

### Prerequisites
- Python $\ge 3.12$
- Linux Kernel $\ge 5.10$ recommended for `io_uring` features (fallback supported on Windows / macOS for development).
- `git`, `make`, `uv` or `pip`

### Workspace Setup
```bash
# 1. Clone the repository
git clone https://github.com/seismael/steve-simulator.git
cd steve-simulator

# 2. Create virtual environment and install in editable mode
python -m venv .venv
source .venv/bin/activate  # Or .venv\Scripts\Activate.ps1 on Windows
pip install -e ".[dev]"

# 3. Verify test suite
pytest -v
```

---

## 4. Quality Gates & Verification Commands

Before opening a pull request, ensure all checks pass:

```bash
# Run static analysis and formatting checks
ruff check steve/ tests/ scripts/ deploy/ usecases/
ruff format --check steve/ tests/ scripts/ deploy/ usecases/

# Run strict type checking
mypy steve/ tests/ scripts/

# Run complete test suite (62 tests)
pytest -v

# Run multi-subsystem performance benchmark suite
python tests/benchmark_suite.py

# Rebuild and validate documentation DAG
python scripts/validate_docs.py
python scripts/build_doc_graph.py
```

---

## 5. Pull Request Workflow

1. **Fork & Branch:** Create a feature branch from `master` (`git checkout -b feat/my-feature`).
2. **Test-Driven Development (TDD):** Propose or write tests under `tests/` before implementing core logic.
3. **Commit Messages:** Follow [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat(adapter): add NVMe-oF RDMA target adapter`
   - `fix(mutator): prevent memoryview leak on ring buffer cycle`
   - `docs(lld): document 64-bucket HDR logarithmic collector`
4. **Submit PR:** Open a PR against `master`. Ensure CI checks pass.

---

## 6. Reporting Issues & Requesting Features

- **Bug Reports:** Provide a minimal reproducible example with host OS, kernel version, Python version, and logs.
- **Feature Requests:** Open an Issue outlining the business motivation, proposed protocol or subsystem, and expected throughput SLA.
