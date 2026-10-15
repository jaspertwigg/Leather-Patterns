import importlib
import os

import psycopg
import pytest
from fastapi.testclient import TestClient

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://root:devpass@127.0.0.1:5432/leather_patterns_test"
)


@pytest.fixture
def client(monkeypatch):
    """A TestClient backed by the test Postgres database, wiped clean
    before each test so tests don't see each other's rows.
    """
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)

    conn = psycopg.connect(TEST_DATABASE_URL)
    conn.execute("DROP TABLE IF EXISTS patterns")
    conn.commit()
    conn.close()

    from app import main as main_module

    importlib.reload(main_module)
    with TestClient(main_module.app) as c:
        yield c
