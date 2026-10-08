import json

import pytest

from benchctl.cli import main


@pytest.fixture
def run(config_path, tmp_path, monkeypatch):
    monkeypatch.delenv("BENCH_SIM_FAULTS", raising=False)
    reports = tmp_path / "reports"

    def _run(*args, faults=None):
        if faults:
            monkeypatch.setenv("BENCH_SIM_FAULTS", faults)
        code = main(["--bench", "sim-bench", "--config", str(config_path), "--reports", str(reports), *args])
        return code, reports

    return _run


def test_prepare_passes(run, image):
    code, reports = run("prepare", "--image", str(image), "--version", "1.4.2")
    assert code == 0
    report = json.loads((reports / "prepare.json").read_text())
    assert report["passed"]
    assert [s["step"] for s in report["steps"]] == ["restart", "health", "flash"]


def test_health_failure_stops_before_flash(run, image):
    code, reports = run("prepare", "--image", str(image), "--version", "1.4.2", faults="no_heartbeat")
    assert code == 1
    report = json.loads((reports / "prepare.json").read_text())
    assert [s["step"] for s in report["steps"]] == ["restart", "health"]


def test_single_step_report_name(run):
    code, reports = run("health")
    assert code == 0
    assert (reports / "health.json").exists()


def test_unknown_bench_exit_code(config_path, tmp_path):
    assert main(["--bench", "ghost", "--config", str(config_path), "health"]) == 2


def test_bench_required(config_path, monkeypatch):
    monkeypatch.delenv("BENCH_NAME", raising=False)
    assert main(["--config", str(config_path), "health"]) == 2
