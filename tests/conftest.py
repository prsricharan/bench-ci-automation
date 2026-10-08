from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def config_path() -> Path:
    return ROOT / "config" / "benches.yaml"


@pytest.fixture
def image(tmp_path: Path) -> Path:
    img = tmp_path / "ecu_app_1.4.2.bin"
    img.write_bytes(b"\x00" * 1024)
    return img
