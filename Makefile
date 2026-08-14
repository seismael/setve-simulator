.PHONY: help install lint format typecheck test benchmark usecases docs-index docs-validate clean

PYTHON ?= python3

help:
	@echo "SETVE Development & Automation Commands:"
	@echo "  make install        Install package and dev dependencies in editable mode"
	@echo "  make lint           Run Ruff linter checks across all source directories"
	@echo "  make format         Auto-format codebase with Ruff"
	@echo "  make typecheck      Run Mypy strict type checking"
	@echo "  make test           Execute complete automated test suite (40 tests)"
	@echo "  make benchmark      Run comprehensive multi-subsystem benchmark suite"
	@echo "  make usecases       Execute all standalone production use case recipes"
	@echo "  make docs-validate  Validate YAML frontmatter and document DAG references"
	@echo "  make docs-index     Rebuild .index/graph.json for AI Agent RAG"
	@echo "  make clean          Remove compiled bytecode, build artifacts, and caches"

install:
	$(PYTHON) -m pip install -e ".[dev]"

lint:
	ruff check setve/ tests/ scripts/ deploy/ usecases/

format:
	ruff format setve/ tests/ scripts/ deploy/ usecases/

typecheck:
	mypy setve/ tests/ scripts/

test:
	pytest tests/ -v

benchmark:
	$(PYTHON) tests/benchmark_suite.py

usecases:
	$(PYTHON) usecases/usecase_01_storage_stress.py
	$(PYTHON) usecases/usecase_02_dedup_compression.py
	$(PYTHON) usecases/usecase_03_prometheus_monitoring.py
	$(PYTHON) usecases/usecase_04_ebpf_triangulation.py
	$(PYTHON) usecases/usecase_05_ai_vector_s3.py
	$(PYTHON) usecases/usecase_06_ai_kv_cache_checkpointing.py
	$(PYTHON) usecases/usecase_07_multitenant_qos_noisy_neighbor.py
	$(PYTHON) usecases/usecase_08_chaos_node_failure.py
	$(PYTHON) usecases/usecase_09_storage_tiering_lifecycle.py
	$(PYTHON) usecases/usecase_10_tail_latency_microburst.py


docs-index:
	$(PYTHON) scripts/build_doc_graph.py

docs-validate:
	$(PYTHON) scripts/validate_docs.py

clean:
	rm -rf build/ dist/ *.egg-info .mypy_cache .pytest_cache .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +

