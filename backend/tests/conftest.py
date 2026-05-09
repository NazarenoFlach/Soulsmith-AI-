from pathlib import Path

import pytest


@pytest.fixture
def settings_data_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "app" / "data"
