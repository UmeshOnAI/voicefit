"""Task 1 tests for the db.py query layer that tools.py (Task 2) builds on.

The brief's four "Done when" checks (alias resolution, seed count 19, last RDL
80 kg [5,5,5], reset after extra rows) live in tests/test_db.py; this file
covers the query functions themselves. Uses the shared fresh_db fixture.
"""
import json
import sqlite3

import pytest

import app.db as db


def test_get_last_session_returns_newest(db_file):
    s = db.get_last_session("romanian_deadlift")
    assert s["weight_kg"] == 80.0
    assert s["reps"] == [5, 5, 5]
    assert s["mood"] == "active"
    assert s["is_seed"] is True
    assert db.get_last_session("overhead_press") is None


def test_get_previous_session(db_file):
    last = db.get_last_session("romanian_deadlift")
    prev = db.get_previous_session("romanian_deadlift", last["performed_at"], last["id"])
    assert prev["weight_kg"] == 80.0
    assert prev["reps"] == [5, 4, 4]  # the 7-days-ago row
    oldest = db.list_sessions("romanian_deadlift")[-1]
    assert db.get_previous_session("romanian_deadlift", oldest["performed_at"], oldest["id"]) is None


def test_list_sessions_newest_first_and_limit(db_file):
    rows = db.list_sessions("bench_press")
    assert len(rows) == 8
    assert rows[0]["weight_kg"] == 62.5 and rows[0]["reps"] == [8, 8, 8]  # 2 days ago
    assert rows[-1]["weight_kg"] == 60.0 and rows[-1]["reps"] == [8, 8, 8]  # 27 days ago
    assert len(db.list_sessions("bench_press", limit=4)) == 4
    assert len(db.list_sessions()) == 19


def test_insert_session_and_duplicate_turn(db_file):
    s, created = db.insert_session("lunge", 20.0, [5, 5], mood="low", turn_id="t1")
    assert created is True
    assert s["id"] >= 1 and s["is_seed"] is False
    again, created2 = db.insert_session("lunge", 99.0, [1], mood="pumped", turn_id="t1")
    assert created2 is False
    assert again["id"] == s["id"]
    assert again["weight_kg"] == 20.0  # original row untouched
    assert db.count_sessions() == 20


def test_insert_session_null_turn_id_allows_many(db_file):
    db.insert_session("lunge", 20.0, [5], turn_id=None)
    db.insert_session("lunge", 22.0, [5], turn_id=None)
    assert db.count_sessions() == 21


def test_sessions_with_mood(db_file):
    low = db.sessions_with_mood("low")
    assert len(low) == 7  # 4 RDL + 3 bench in the seed
    assert all(s["mood"] == "low" for s in low)


def test_latest_non_seed_today_and_mood_today(db_file):
    assert db.latest_non_seed_today() is None  # only seed rows exist
    db.insert_session("bench_press", 60.0, [8, 8, 8], mood="low", turn_id="t-mood")
    s = db.latest_non_seed_today()
    assert s["exercise_id"] == "bench_press" and s["mood"] == "low"
    n = db.set_mood_today("pumped")
    assert n == 1
    assert db.latest_non_seed_today()["mood"] == "pumped"
    # seed rows are never touched by set_mood_today: the 7 seed 'low' rows stay low
    conn = sqlite3.connect(db_file)
    assert conn.execute(
        "SELECT COUNT(*) FROM sessions WHERE is_seed = 1 AND mood = 'low'"
    ).fetchone()[0] == 7
    conn.close()


def test_delete_non_seed(db_file):
    db.insert_session("lunge", 20.0, [5], turn_id="t-del")
    assert db.count_sessions() == 20
    assert db.delete_non_seed() == 1
    assert db.count_sessions() == 19


def test_init_db_seeds_once(tmp_path):
    p = tmp_path / "new.db"
    db.init_db(p)
    assert db.count_sessions(p) == 19
    db.insert_session("lunge", 20.0, [5], turn_id="t-init", path=p)
    db.init_db(p)  # must not wipe or reseed an existing db
    assert db.count_sessions(p) == 20


def test_reset_db_on_explicit_path(tmp_path):
    p = tmp_path / "other.db"
    db.reset_db(p)
    assert db.count_sessions(p) == 19
    assert db.resolve_exercise("RDLs", p) == "romanian_deadlift"
    conn = sqlite3.connect(p)
    reps = conn.execute("SELECT reps FROM sessions LIMIT 1").fetchone()[0]
    assert isinstance(json.loads(reps), list)
    conn.close()


def test_resolve_exercise_case_and_exactness(db_file):
    assert db.resolve_exercise("  RdLs ") == "romanian_deadlift"
    assert db.resolve_exercise("Overhead Press") == "overhead_press"
    assert db.resolve_exercise("bench_press") == "bench_press"
    assert db.resolve_exercise("press") is None
    assert db.resolve_exercise("") is None
    assert db.resolve_exercise(None) is None
