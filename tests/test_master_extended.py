"""Extended Unit Tests for MultiCoreOrchestrator and Worker Failure Handling."""

import tempfile
from unittest.mock import MagicMock, patch

import pytest

from steve.exceptions import WorkerCrashError
from steve.orchestrator.master import MultiCoreOrchestrator
from steve.payload.blueprint import WorkloadBlueprint
from steve.validation.reporter import WorkerTelemetryResult


def test_orchestrator_worker_crash_error_propagation() -> None:
    """Verify MultiCoreOrchestrator raises WorkerCrashError when worker reports failure."""
    orchestrator = MultiCoreOrchestrator(core_ids=[0])

    blueprint = WorkloadBlueprint.from_dict(
        {
            "run_id": "crash-test-01",
            "target_uri": "posix://test.dat",
            "block_size_bytes": 4096,
            "entropy_ratio": 0.5,
            "target_throughput_gbps": 1.0,
            "duration_seconds": 0.1,
            "global_seed": 42,
        }
    )

    failed_result = WorkerTelemetryResult(
        core_id=0,
        node_id="test-node",
        total_ops=0,
        total_bytes=0,
        duration_sec=0.1,
        p50_ms=0.0,
        p90_ms=0.0,
        p99_ms=0.0,
        p999_ms=0.0,
        throughput_gbps=0.0,
        error_message="Simulated NVMe controller panic",
    )

    with patch("multiprocessing.Process") as mock_proc:
        mock_instance = MagicMock()
        mock_instance.exitcode = 0
        mock_proc.return_value = mock_instance

        with patch("multiprocessing.Queue") as mock_q:
            q_instance = MagicMock()
            q_instance.empty.side_effect = [False, True]
            q_instance.get_nowait.return_value = failed_result
            mock_q.return_value = q_instance

            with pytest.raises(WorkerCrashError, match="Simulated NVMe controller panic"):
                orchestrator.start(blueprint)


def test_orchestrator_cli_main() -> None:
    """Verify master CLI main function runs cleanly."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_file = f"{tmp_dir}/cli_test.dat"
        with patch(
            "steve.payload.blueprint.WorkloadBlueprint.from_dict",
            return_value=WorkloadBlueprint.from_dict(
                {
                    "run_id": "cli-test",
                    "target_uri": f"posix://{test_file}",
                    "block_size_bytes": 4096,
                    "entropy_ratio": 0.5,
                    "target_throughput_gbps": 0.1,
                    "duration_seconds": 0.1,
                    "global_seed": 1,
                }
            ),
        ):
            from steve.orchestrator.master import main

            # Execute main without raising
            main()
