"""Shared pytest fixtures.

DATA_DIR must be set before importing the app modules (config.py runs
DATA_DIR.mkdir() at import, and the default /app/data is not writable locally).
Each test gets a fresh, isolated SQLite file via monkeypatching db.DB_PATH.
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Point app config at a writable temp dir BEFORE importing config/main/db.
_SESSION_DIR = Path(tempfile.mkdtemp(prefix="expense-tests-"))
os.environ.setdefault("DATA_DIR", str(_SESSION_DIR))

# Make backend package importable regardless of pytest's cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def client(tmp_path, monkeypatch):
    """TestClient backed by a fresh seeded DB per test."""
    import config
    import db
    import main
    from fastapi.testclient import TestClient

    db_file = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", db_file)
    monkeypatch.setattr(config, "DB_PATH", db_file)
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)

    db.init_db()
    db.migrate_schema()
    db.migrate_json()
    db.seed_defaults()

    return TestClient(main.app)


@pytest.fixture
def wallet_id(client):
    """Id of the first seeded wallet."""
    return client.get("/api/wallets").json()[0]["id"]


@pytest.fixture
def category_id(client):
    """Id of the first seeded category."""
    return client.get("/api/categories").json()[0]["id"]
