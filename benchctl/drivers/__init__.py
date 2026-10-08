from __future__ import annotations

from ..config import BenchConfig
from .base import BenchDriver, BenchError
from .simulated import SimulatedBench

__all__ = ["BenchDriver", "BenchError", "SimulatedBench", "make_driver"]


def make_driver(cfg: BenchConfig) -> BenchDriver:
    """Build the driver named by the bench's ``backend`` setting."""
    if cfg.backend == "simulated":
        return SimulatedBench()
    if cfg.backend == "winrm":
        from .winrm import WinRMBench

        return WinRMBench(cfg)
    raise BenchError(f"Unknown backend '{cfg.backend}' for bench '{cfg.name}'")
