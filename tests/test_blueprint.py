"""Tests for WorkloadBlueprint Domain Model."""

from setve.payload.blueprint import WorkloadBlueprint


def test_blueprint_parsing() -> None:
    """Verify blueprint parses dictionaries accurately."""
    data = {
        "run_id": "integration-test-run",
        "target_uri": "iouring:///dev/nvme0n1",
        "block_size_bytes": 4096,
        "target_throughput_gbps": 200,
    }
    
    blueprint = WorkloadBlueprint.from_dict(data)
    
    assert blueprint.run_id == "integration-test-run"
    assert blueprint.target_uri == "iouring:///dev/nvme0n1"
    assert blueprint.block_size_bytes == 4096
    
    # Defaults
    assert blueprint.entropy_ratio == 0.8
    assert blueprint.target_throughput_gbps == 200
    assert blueprint.duration_seconds == 30
    assert blueprint.global_seed == 42
