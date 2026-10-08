"""Reference backend for real Windows bench PCs, driven over WinRM.

This is the integration point for physical hardware. It reboots the bench
PC with PowerShell and calls a small helper script on the bench
(``bench_agent.py``) that talks to the power supply, CAN interface and
flashing tool installed there. The helper is bench-specific: adapt
``AGENT`` and the commands below to the tools on your rig.

Requires ``pip install pywinrm`` and these environment variables (set them
as masked CI/CD variables, never in the repo):
    BENCH_WINRM_USER, BENCH_WINRM_PASSWORD
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from ..config import BenchConfig
from .base import BenchDriver, BenchError

AGENT = r"C:\bench\venv\Scripts\python.exe C:\bench\bench_agent.py"


class WinRMBench(BenchDriver):
    def __init__(self, cfg: BenchConfig):
        try:
            import winrm  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise BenchError("The winrm backend needs: pip install pywinrm") from exc

        user = os.environ.get("BENCH_WINRM_USER")
        password = os.environ.get("BENCH_WINRM_PASSWORD")
        if not user or not password:
            raise BenchError("Set BENCH_WINRM_USER and BENCH_WINRM_PASSWORD")

        self.cfg = cfg
        self._session = winrm.Session(
            f"https://{cfg.host}:5986/wsman",
            auth=(user, password),
            transport="ntlm",
            server_cert_validation="validate",
        )

    # --- helpers ------------------------------------------------------
    def _ps(self, script: str):
        return self._session.run_ps(script)

    def _agent(self, *args: str) -> dict:
        cmd = " ".join([AGENT, *args, "--can", self.cfg.can_channel, "--json"])
        result = self._ps(cmd)
        if result.status_code != 0:
            raise BenchError(result.std_err.decode(errors="replace").strip())
        return json.loads(result.std_out)

    # --- bench PC -----------------------------------------------------
    def reboot(self) -> None:
        # The connection drops as the machine goes down; that is expected.
        try:
            self._ps("Restart-Computer -Force")
        except Exception:
            pass

    def is_reachable(self) -> bool:
        try:
            return self._ps("$true").status_code == 0
        except Exception:
            return False

    # --- hardware -----------------------------------------------------
    def read_psu_voltage(self) -> float:
        return float(self._agent("psu-voltage")["voltage"])

    def can_interface_up(self) -> bool:
        return bool(self._agent("can-status")["up"])

    def ecu_heartbeat(self, timeout_s: float) -> bool:
        return bool(self._agent("heartbeat", "--timeout", str(timeout_s))["seen"])

    def read_active_dtcs(self) -> list[str]:
        return list(self._agent("read-dtcs")["dtcs"])

    # --- software -----------------------------------------------------
    def flash(self, image: Path) -> None:
        # The image is expected to be on a share the bench can read.
        self._agent("flash", "--image", str(image))

    def read_software_version(self) -> str:
        return str(self._agent("sw-version")["version"])
