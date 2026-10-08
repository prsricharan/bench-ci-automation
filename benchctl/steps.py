"""Pipeline steps: restart the bench, gate on health, flash and verify.

Each step returns a ``StepResult`` instead of raising, so the CLI can write
a complete report even when a step fails.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .config import BenchConfig
from .drivers.base import BenchDriver, BenchError


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


@dataclass
class StepResult:
    step: str
    passed: bool
    duration_s: float
    checks: list[CheckResult] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _timed(step: str, fn: Callable[[], list[CheckResult]]) -> StepResult:
    start = time.monotonic()
    try:
        checks = fn()
        passed = all(c.passed for c in checks)
        return StepResult(step, passed, round(time.monotonic() - start, 3), checks)
    except BenchError as exc:
        return StepResult(step, False, round(time.monotonic() - start, 3), error=str(exc))


# --- restart ------------------------------------------------------------
def restart_bench(
    driver: BenchDriver,
    cfg: BenchConfig,
    sleep: Callable[[float], None] = time.sleep,
) -> StepResult:
    """Reboot the bench PC and wait until it accepts commands again."""

    def run() -> list[CheckResult]:
        driver.reboot()
        waited = 0.0
        while waited < cfg.reboot_timeout_s:
            sleep(cfg.poll_interval_s)
            waited += cfg.poll_interval_s
            if driver.is_reachable():
                return [CheckResult("bench_pc_online", True, f"back online after ~{waited:.0f}s")]
        return [
            CheckResult(
                "bench_pc_online",
                False,
                f"not reachable within {cfg.reboot_timeout_s:.0f}s after reboot",
            )
        ]

    return _timed("restart", run)


# --- health gate --------------------------------------------------------
def health_check(driver: BenchDriver, cfg: BenchConfig) -> StepResult:
    """Verify the rig is fit to test on before spending time on a run."""
    limits = cfg.limits

    def run() -> list[CheckResult]:
        checks = []

        volts = driver.read_psu_voltage()
        in_range = limits.psu_voltage_min <= volts <= limits.psu_voltage_max
        checks.append(
            CheckResult(
                "psu_voltage",
                in_range,
                f"{volts:.2f} V (allowed {limits.psu_voltage_min}-{limits.psu_voltage_max} V)",
            )
        )

        can_up = driver.can_interface_up()
        checks.append(CheckResult("can_interface", can_up, f"{cfg.can_channel} {'up' if can_up else 'down'}"))

        beat = driver.ecu_heartbeat(limits.heartbeat_timeout_s)
        checks.append(
            CheckResult(
                "ecu_heartbeat",
                beat,
                f"{cfg.ecu_id} {'responding' if beat else f'silent for {limits.heartbeat_timeout_s}s'}",
            )
        )

        dtcs = driver.read_active_dtcs() if beat else []
        checks.append(
            CheckResult(
                "active_dtcs",
                len(dtcs) <= limits.max_active_dtcs,
                f"{len(dtcs)} active" + (f": {', '.join(dtcs)}" if dtcs else ""),
            )
        )
        return checks

    return _timed("health", run)


# --- flash --------------------------------------------------------------
def flash_and_verify(driver: BenchDriver, image: Path, expected_version: str) -> StepResult:
    """Flash an image and confirm the ECU now runs the expected version."""

    def run() -> list[CheckResult]:
        driver.flash(Path(image))
        actual = driver.read_software_version()
        return [
            CheckResult("flash", True, f"flashed {Path(image).name}"),
            CheckResult(
                "version_match",
                actual == expected_version,
                f"ECU reports {actual}, expected {expected_version}",
            ),
        ]

    return _timed("flash", run)
