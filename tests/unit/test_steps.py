import pytest

from benchctl.config import BenchConfig
from benchctl.drivers import SimulatedBench
from benchctl.steps import flash_and_verify, health_check, restart_bench

CFG = BenchConfig(name="t", host="localhost", reboot_timeout_s=10, poll_interval_s=1)


def no_sleep(_):
    pass


def failed_checks(result):
    return {c.name for c in result.checks if not c.passed}


# --- restart ------------------------------------------------------------
def test_restart_waits_for_bench():
    driver = SimulatedBench(faults=set(), boot_polls=3)
    result = restart_bench(driver, CFG, sleep=no_sleep)
    assert result.passed
    assert driver.boot_count == 1
    assert "~4s" in result.checks[0].detail


def test_restart_times_out():
    result = restart_bench(SimulatedBench(faults={"unreachable"}), CFG, sleep=no_sleep)
    assert not result.passed
    assert failed_checks(result) == {"bench_pc_online"}


# --- health gate --------------------------------------------------------
def test_healthy_bench_passes():
    result = health_check(SimulatedBench(faults=set()), CFG)
    assert result.passed
    assert len(result.checks) == 4


@pytest.mark.parametrize(
    "fault, expected_failures",
    [
        ("psu_low", {"psu_voltage", "ecu_heartbeat"}),
        ("can_down", {"can_interface", "ecu_heartbeat"}),
        ("no_heartbeat", {"ecu_heartbeat"}),
        ("dtc", {"active_dtcs"}),
    ],
)
def test_health_gate_catches_fault(fault, expected_failures):
    result = health_check(SimulatedBench(faults={fault}), CFG)
    assert not result.passed
    assert failed_checks(result) == expected_failures


# --- flash --------------------------------------------------------------
def test_flash_and_verify(image):
    result = flash_and_verify(SimulatedBench(faults=set()), image, "1.4.2")
    assert result.passed


def test_flash_failure_is_reported(image):
    result = flash_and_verify(SimulatedBench(faults={"flash_fail"}), image, "1.4.2")
    assert not result.passed
    assert "aborted" in result.error


def test_version_mismatch(image):
    result = flash_and_verify(SimulatedBench(faults={"bad_version"}), image, "1.4.2")
    assert not result.passed
    assert failed_checks(result) == {"version_match"}


def test_missing_image(tmp_path):
    result = flash_and_verify(SimulatedBench(faults=set()), tmp_path / "missing.bin", "1.4.2")
    assert not result.passed
    assert "not found" in result.error


def test_unknown_fault_rejected(monkeypatch):
    monkeypatch.setenv("BENCH_SIM_FAULTS", "psu_low,gremlins")
    with pytest.raises(ValueError, match="gremlins"):
        SimulatedBench()
