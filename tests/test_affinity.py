"""Unit tests for CPU affinity and hardware core topology utilities."""

from unittest.mock import MagicMock, patch

from steve.orchestrator.affinity import available_cores, pin_to_core


def test_affinity_available_cores() -> None:
    """Verify available_cores returns valid core IDs on active platform."""
    cores = available_cores()
    assert isinstance(cores, list)
    assert len(cores) >= 1
    assert all(isinstance(c, int) for c in cores)


def test_pin_to_core_handling() -> None:
    """Verify pin_to_core gracefully executes on all platforms without raising errors."""
    # Test on host platform
    pin_to_core(0)

    # Test with mocked sched_setaffinity
    with patch("os.sched_setaffinity", create=True, new=MagicMock()) as mock_set:
        pin_to_core(2)
        mock_set.assert_called_once_with(0, {2})


def test_available_cores_mocked_affinity() -> None:
    """Verify available_cores reads from sched_getaffinity when present."""
    with patch("os.sched_getaffinity", create=True, return_value={0, 1, 2, 3}):
        cores = available_cores()
        assert set(cores) == {0, 1, 2, 3}
