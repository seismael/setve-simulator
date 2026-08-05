.PHONY: help install lint typecheck test benchmark docs-index docs-validate clean

PYTHON ?= python3

help:
	@echo "SETVE Development Commands:"
	@echo "  make install      Install package and dev dependencies"
	@echo "  make lint         Run Ruff linter & formatter checks"
	@echo "  make typecheck    Run Mypy strict type checking"
	@echo "  make test         Execute test suite"
	@echo "  make benchmark    Run hot-path throughput benchmarks"
	@echo "  make docs-index   Rebuild .index/graph.json for AI Agent RAG"

install:
	$(PYTHON) -m pip install -e ".[dev]"

lint:
	ruff check setve/ tests/ scripts/
	ruff format --check setve/ tests/ scripts/

typecheck:
	mypy setve/ tests/ scripts/

test:
	pytest tests/ -v

benchmark:
	python3 tests/benchmark_adapters.py

docs-index:
	python3 scripts/build_doc_graph.py

docs-validate:
	python3 scripts/validate_docs.py

clean:
	rm -rf build/ dist/ *.egg-info .mypy_cache .pytest_cache .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
