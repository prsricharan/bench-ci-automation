import pytest

from benchctl.config import ConfigError, get_bench, load_benches


def test_loads_inventory(config_path):
    benches = load_benches(config_path)
    assert {"sim-bench", "hil-bench-01", "hil-bench-02"} <= set(benches)
    assert benches["hil-bench-01"].backend == "winrm"
    assert benches["hil-bench-01"].limits.max_active_dtcs == 0


def test_defaults_applied(config_path):
    bench = get_bench(config_path, "hil-bench-02")
    assert bench.limits.psu_voltage_min == 11.5
    assert bench.reboot_timeout_s == 300.0


def test_unknown_bench(config_path):
    with pytest.raises(ConfigError, match="Unknown bench"):
        get_bench(config_path, "nope")


def test_missing_host(tmp_path):
    cfg = tmp_path / "b.yaml"
    cfg.write_text("benches:\n  x:\n    backend: simulated\n")
    with pytest.raises(ConfigError, match="missing 'host'"):
        load_benches(cfg)


def test_unknown_key(tmp_path):
    cfg = tmp_path / "b.yaml"
    cfg.write_text("benches:\n  x:\n    host: h\n    colour: red\n")
    with pytest.raises(ConfigError, match="colour"):
        load_benches(cfg)
