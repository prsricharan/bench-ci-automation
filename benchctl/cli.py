"""Command-line entry point used by the CI jobs.

    benchctl --bench hil-bench-01 restart
    benchctl --bench hil-bench-01 health
    benchctl --bench hil-bench-01 flash --image build/ecu_app_1.4.2.bin --version 1.4.2
    benchctl --bench hil-bench-01 prepare --image ... --version ...   # all three

Each command writes ``reports/<step>.json`` and exits non-zero on failure,
so a failed gate stops the pipeline before the test stage.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .config import ConfigError, get_bench
from .drivers import BenchError, make_driver
from .steps import StepResult, flash_and_verify, health_check, restart_bench

DEFAULT_CONFIG = os.environ.get("BENCH_CONFIG", "config/benches.yaml")


def _print(result: StepResult) -> None:
    status = "PASS" if result.passed else "FAIL"
    print(f"[{status}] {result.step} ({result.duration_s}s)")
    for check in result.checks:
        mark = "ok " if check.passed else "!! "
        print(f"    {mark}{check.name}: {check.detail}")
    if result.error:
        print(f"    !! error: {result.error}")


def _write(report_dir: Path, bench: str, results: list[StepResult]) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    name = results[0].step if len(results) == 1 else "prepare"
    path = report_dir / f"{name}.json"
    payload = {
        "bench": bench,
        "passed": all(r.passed for r in results),
        "steps": [r.to_dict() for r in results],
    }
    path.write_text(json.dumps(payload, indent=2))
    return path


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="benchctl", description=__doc__.splitlines()[0])
    p.add_argument("--bench", default=os.environ.get("BENCH_NAME"), help="bench name from the config")
    p.add_argument("--config", default=DEFAULT_CONFIG, help="bench inventory YAML")
    p.add_argument("--reports", default="reports", help="directory for JSON reports")

    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("restart", help="reboot the bench PC and wait for it")
    sub.add_parser("health", help="run the hardware health gate")
    for name in ("flash", "prepare"):
        sp = sub.add_parser(name, help="flash and verify" if name == "flash" else "restart + health + flash")
        sp.add_argument("--image", required=True, type=Path)
        sp.add_argument("--version", required=True, dest="expected_version")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.bench:
        print("error: --bench or BENCH_NAME is required", file=sys.stderr)
        return 2

    try:
        cfg = get_bench(args.config, args.bench)
        driver = make_driver(cfg)
    except (ConfigError, BenchError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    results: list[StepResult] = []
    if args.command in ("restart", "prepare"):
        results.append(restart_bench(driver, cfg))
    if args.command in ("health", "prepare") and all(r.passed for r in results):
        results.append(health_check(driver, cfg))
    if args.command in ("flash", "prepare") and all(r.passed for r in results):
        results.append(flash_and_verify(driver, args.image, args.expected_version))

    for r in results:
        _print(r)
    report = _write(Path(args.reports), cfg.name, results)
    print(f"report: {report}")
    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
