"""Driver interface every bench backend implements.

The pipeline logic (restart, health gate, flash, test) only talks to this
interface, so the same code runs against real hardware or the simulator.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class BenchError(RuntimeError):
    """A bench operation failed in a way the pipeline should report."""


class BenchDriver(ABC):
    # --- bench PC -----------------------------------------------------
    @abstractmethod
    def reboot(self) -> None:
        """Request a reboot of the bench PC (returns immediately)."""

    @abstractmethod
    def is_reachable(self) -> bool:
        """True once the bench PC is back up and accepting commands."""

    # --- hardware -----------------------------------------------------
    @abstractmethod
    def read_psu_voltage(self) -> float:
        """Programmable power supply output voltage, in volts."""

    @abstractmethod
    def can_interface_up(self) -> bool:
        """True if the CAN interface to the ECU is up."""

    @abstractmethod
    def ecu_heartbeat(self, timeout_s: float) -> bool:
        """True if the ECU's periodic heartbeat frame is seen within timeout."""

    @abstractmethod
    def read_active_dtcs(self) -> list[str]:
        """Active diagnostic trouble codes reported by the ECU."""

    # --- software -----------------------------------------------------
    @abstractmethod
    def flash(self, image: Path) -> None:
        """Flash a software image onto the ECU."""

    @abstractmethod
    def read_software_version(self) -> str:
        """Software version currently running on the ECU."""
