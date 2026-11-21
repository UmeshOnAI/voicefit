"""Shared pytest setup for the VoiceFit contract tests.

Puts the repository root on sys.path so `import app.db` works, and gives
every test a fresh, isolated, seeded database in a temporary directory.
"""
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """Run each test in tmp_path with a freshly seeded voicefit.db.

    Contract assumed from docs/BUILD-BRIEF.md: app/db.py exposes DB_PATH
    (the sqlite file, voicefit.db) and every db function takes an optional
    path that defaults to the *current* DB_PATH at call time, so tests can
    point the app at a temporary file. Skips while app/db.py is not merged.
    """
    monkeypatch.chdir(tmp_path)
    try:
        import app.db as db
    except ImportError:
        pytest.skip("app/db.py does not exist yet (Task 1 not merged)")
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "voicefit.db", raising=False)
    db.reset_db()
    return tmp_path / "voicefit.db"


@pytest.fixture
def db_file(fresh_db):
    """Path of the test database."""
    return fresh_db


@pytest.fixture
def sql(db_file):
    """Raw sqlite3 connection to the test database.

    The schema is specified in docs/BUILD-BRIEF.md, so tests may read and
    write rows directly with SQL.
    """
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()
