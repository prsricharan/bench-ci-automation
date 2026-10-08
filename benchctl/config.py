"""Bench inventory loaded from YAML."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class HealthLimits:
    """Pass/fail thresholds for the pre-test health gate."""

    psu_voltage_min: float = 11.5
    psu_voltage_max: float = 14.5
    heartbeat_timeout_s: float = 2.0
    max_active_dtcs: int = 0


@dataclass(frozen=True)
class BenchConfig:
    """One physical (or simulated) test bench."""

    name: str
    host: str
    backend: str = "simulated"
    can_channel: str = "can0"
    ecu_id: str = "ECU_A"
    reboot_timeout_s: float = 300.0
    poll_interval_s: float = 5.0
    limits: HealthLimits = field(default_factory=HealthLimits)


class ConfigError(ValueError):
    """Raised when the bench inventory is missing or malformed."""


def load_benches(path: str | Path) -> dict[str, BenchConfig]:
    """Parse a bench inventory file into ``{name: BenchConfig}``."""
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"Bench config not found: {path}")

    data = yaml.safe_load(path.read_text()) or {}
    raw_benches = data.get("benches")
    if not isinstance(raw_benches, dict) or not raw_benches:
        raise ConfigError(f"No 'benches' section in {path}")

    benches: dict[str, BenchConfig] = {}
    for name, raw in raw_benches.items():
        raw = dict(raw or {})
        if "host" not in raw:
            raise ConfigError(f"Bench '{name}' is missing 'host'")
        limits = HealthLimits(**raw.pop("limits", {}))
        try:
            benches[name] = BenchConfig(name=name, limits=limits, **raw)
        except TypeError as exc:
            raise ConfigError(f"Bench '{name}': {exc}") from exc
    return benches


def get_bench(path: str | Path, name: str) -> BenchConfig:
    benches = load_benches(path)
    if name not in benches:
        known = ", ".join(sorted(benches))
        raise ConfigError(f"Unknown bench '{name}'. Known benches: {known}")
    return benches[name]
