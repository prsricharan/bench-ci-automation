"""Simulated bench backend.

Behaves like a real bench (reboots take a few polls, the ECU only reports a
heartbeat when powered and the CAN link is up) so the full pipeline can run
in CI with no hardware. Faults are injected with the ``BENCH_SIM_FAULTS``
environment variable, e.g. ``BENCH_SIM_FAULTS=psu_low,no_heartbeat``.

Supported faults:
    unreachable   bench PC never comes back after a reboot
    psu_low       power supply reads 9.8 V
    can_down      CAN interface is down (no heartbeat either)
    no_heartbeat  ECU is silent on the bus
    dtc           ECU reports an active trouble code
    flash_fail    flashing aborts part-way
    bad_version   ECU reports a different version after flashing
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from .base import BenchDriver, BenchError

KNOWN_FAULTS = {
    "unreachable",
    "psu_low",
    "can_down",
    "no_heartbeat",
    "dtc",
    "flash_fail",
    "bad_version",
}

_VERSION_RE = re.compile(r"(\d+\.\d+\.\d+)")


def faults_from_env() -> set[str]:
    raw = os.environ.get("BENCH_SIM_FAULTS", "")
    faults = {f.strip() for f in raw.split(",") if f.strip()}
    unknown = faults - KNOWN_FAULTS
    if unknown:
        raise ValueError(f"Unknown simulated faults: {', '.join(sorted(unknown))}")
    return faults


class SimulatedBench(BenchDriver):
    def __init__(self, faults: set[str] | None = None, boot_polls: int = 2):
        self.faults = set(faults) if faults is not None else faults_from_env()
        self.boot_polls = boot_polls
        self._polls_until_up = 0
        self.boot_count = 0
        self.version = "1.0.0"

    # --- bench PC -----------------------------------------------------
    def reboot(self) -> None:
        self.boot_count += 1
        self._polls_until_up = self.boot_polls

    def is_reachable(self) -> bool:
        if "unreachable" in self.faults:
            return False
        if self._polls_until_up > 0:
            self._polls_until_up -= 1
            return False
        return True

    # --- hardware -----------------------------------------------------
    def read_psu_voltage(self) -> float:
        return 9.8 if "psu_low" in self.faults else 13.5

    def can_interface_up(self) -> bool:
        return "can_down" not in self.faults

    def ecu_heartbeat(self, timeout_s: float) -> bool:
        powered = self.read_psu_voltage() > 10.0
        return powered and self.can_interface_up() and "no_heartbeat" not in self.faults

    def read_active_dtcs(self) -> list[str]:
        return ["U0100"] if "dtc" in self.faults else []

    # --- software -----------------------------------------------------
    def flash(self, image: Path) -> None:
        image = Path(image)
        if not image.is_file():
            raise BenchError(f"Image not found: {image}")
        if "flash_fail" in self.faults:
            raise BenchError("Flash aborted at 63%: ECU did not acknowledge block 41")
        match = _VERSION_RE.search(image.name)
        self.version = match.group(1) if match else "0.0.0"

    def read_software_version(self) -> str:
        return "0.0.0-bad" if "bad_version" in self.faults else self.version
