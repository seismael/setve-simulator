"""Extended Unit Tests for Deploy Module and LocalClusterEmulator CLI Entrypoint."""

from unittest.mock import patch

from deploy.emulator.cluster_runner import main


def test_cluster_runner_cli_main() -> None:
    """Verify deploy emulator cluster_runner main entrypoint parses arguments and runs."""
    with patch(
        "sys.argv",
        [
            "cluster_runner.py",
            "--nodes",
            "2",
            "--cores-per-node",
            "1",
            "--duration",
            "0.2",
            "--rate",
            "1.0",
        ],
    ):
        # Must execute without exception
        main()
