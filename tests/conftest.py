import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A TestClient backed by a fresh, isolated data directory per test --
    reloads app.main so its module-level DATA_DIR/DB_PATH pick up the
    env var rather than whatever a previous test left behind.
    """
    monkeypatch.setenv("LEATHER_PATTERNS_DATA_DIR", str(tmp_path / "data"))
    from app import main as main_module

    importlib.reload(main_module)
    with TestClient(main_module.app) as c:
        yield c
