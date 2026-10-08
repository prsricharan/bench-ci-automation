"""Smoke tests that run ON a bench after it has been prepared.

These use the same driver interface as the pipeline, so they run against
real hardware on a self-hosted runner and against the simulator in CI:

    BENCH_NAME=sim-bench pytest -m bench
"""

import os

import pytest

from benchctl.config import get_bench
from benchctl.drivers import make_driver

pytestmark = pytest.mark.bench


@pytest.fixture(scope="module")
def bench(request):
    name = os.environ.get("BENCH_NAME")
    if not name:
        pytest.skip("BENCH_NAME not set; bench tests need a target bench")
    config = os.environ.get("BENCH_CONFIG", str(request.config.rootpath / "config" / "benches.yaml"))
    cfg = get_bench(config, name)
    return cfg, make_driver(cfg)


def test_ecu_is_alive(bench):
    cfg, driver = bench
    assert driver.ecu_heartbeat(cfg.limits.heartbeat_timeout_s), f"{cfg.ecu_id} not sending heartbeat"


def test_supply_voltage_stable(bench):
    cfg, driver = bench
    readings = [driver.read_psu_voltage() for _ in range(5)]
    assert max(readings) - min(readings) < 0.2, f"supply ripple too high: {readings}"


def test_no_active_dtcs(bench):
    _, driver = bench
    assert driver.read_active_dtcs() == []


def test_running_expected_version(bench):
    _, driver = bench
    expected = os.environ.get("EXPECTED_SW_VERSION")
    if not expected:
        pytest.skip("EXPECTED_SW_VERSION not set")
    assert driver.read_software_version() == expected
