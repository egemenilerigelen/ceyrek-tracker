import json
import os
from datetime import datetime
from pathlib import Path

import pytest

# Testler gerçek %APPDATA% klasörüne dokunmasın, ekran gerektirmesin.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("CEYREK_TAKIP_DATA_DIR", str(tmp_path / "appdata"))
    return tmp_path / "appdata"


@pytest.fixture
def fetched_at():
    return datetime(2026, 10, 29, 16, 41, 0)
