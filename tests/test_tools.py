"""Contract tests for Task 2: app/tools.py.

Written from docs/BUILD-BRIEF.md before the code exists. Every test skips
while app/db.py or app/tools.py is not merged (at run time, so pytest still
collects the tests and exits 0), so main always passes.

Interface assumed from the brief (Tasks 1-2 implement to this):

- tools.TRACE: contextvars.ContextVar holding the current request's trace list
- tools.TURN_ID: contextvars.ContextVar holding the current turn_id
- tools.compare(previous, new) -> {"outcome", "delta_reps"} where previous
  may be None (-> "first") and previous/new are dicts with "weight_kg"
  and "reps"
- tools.get_last_session(exercise) -> dict
- tools.log_session(exercise, weight, unit, reps, mood=None) -> dict
- tools.get_mood_history(mood) -> dict

Every tool call appends {tool, args, result, ms} to TRACE. log_session reads
the current turn_id from TURN_ID for the UNIQUE (turn_id, exercise_id) rule.
"""
import sqlite3
from contextlib import contextmanager

import pytest

try:
    import app.db as db  # noqa: F401  (tools.py builds on db.py)
    import app.tools as tools
    _IMPORT_ERROR = None
except ImportError as exc:
    # Skip at run time, not at collection: a module-level skip leaves pytest
    # with zero collected items and exit code 5, and main must always pass.
    db = tools = None
    _IMPORT_ERROR = exc


@pytest.fixture(autouse=True)
def _skip_while_module_missing():
    if _IMPORT_ERROR is not None:
        pytest.skip(f"app/db.py or app/tools.py not merged yet: {_IMPORT_ERROR}")


@contextmanager
def turn(turn_id):
    """Run tool calls inside one request turn, as main.py does."""
    trace = []
    tok_trace = tools.TRACE.set(trace)
    tok_turn = tools.TURN_ID.set(turn_id)
    try:
        yield trace
    finally:
        tools.TRACE.reset(tok_trace)
        tools.TURN_ID.reset(tok_turn)


def count_sessions(db_file):
    conn = sqlite3.connect(db_file)
    n = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    conn.close()
    return n


# --- compare --------------------------------------------------------------


def test_compare_first_when_no_previous():
    r = tools.compare(None, {"weight_kg": 80.0, "reps": [5, 5, 5]})
    assert r["outcome"] == "first"
    assert r["delta_reps"] is None


def test_compare_weight_up_is_beat_delta_null():
    prev = {"weight_kg": 80.0, "reps": [5, 5, 5]}
    r = tools.compare(prev, {"weight_kg": 82.5, "reps": [5, 5, 5]})
    assert r["outcome"] == "beat"
    assert r["delta_reps"] is None


def test_compare_same_weight_more_reps_is_beat():
    prev = {"weight_kg": 80.0, "reps": [5, 5, 5]}
    r = tools.compare(prev, {"weight_kg": 80.0, "reps": [5, 5, 6]})
    assert r["outcome"] == "beat"
    assert r["delta_reps"] == 1


def test_compare_same_weight_same_reps_is_held():
    prev = {"weight_kg": 80.0, "reps": [5, 5, 5]}
    r = tools.compare(prev, {"weight_kg": 80.0, "reps": [5, 5, 5]})
    assert r["outcome"] == "held"
    assert r["delta_reps"] == 0


def test_compare_same_weight_fewer_reps_is_dropped():
    prev = {"weight_kg": 80.0, "reps": [5, 5, 5]}
    r = tools.compare(prev, {"weight_kg": 80.0, "reps": [5, 5, 4]})
    assert r["outcome"] == "dropped"
    assert r["delta_reps"] == -1


def test_compare_weight_within_005_is_same():
    prev = {"weight_kg": 80.0, "reps": [5, 5, 5]}
    r = tools.compare(prev, {"weight_kg": 80.04, "reps": [5, 5, 5]})
    assert r["outcome"] == "held"
    assert r["delta_reps"] == 0


def test_compare_weight_more_than_005_apart_is_not_same():
    # 80.06 differs from 80.0 by more than 0.05 kg, so the weights are not
    # "the same": heavier is a beat and delta_reps is null.
    prev = {"weight_kg": 80.0, "reps": [5, 5, 5]}
    r = tools.compare(prev, {"weight_kg": 80.06, "reps": [5, 5, 5]})
    assert r["outcome"] == "beat"
    assert r["delta_reps"] is None


# --- log_session: the Task 2 "Done when" checks ----------------------------


def test_log_rdl_80kg_556_is_beat(db_file):
    with turn("t-beat"):
        r = tools.log_session("rdls", 80, "kg", [5, 5, 6])
    assert r["saved"] is True
    assert r["exercise_id"] == "romanian_deadlift"
    assert r["exercise_name"] == "Romanian deadlift"
    assert r["weight_kg"] == 80.0
    assert r["reps"] == [5, 5, 6]
    assert r["total_reps"] == 16
    assert r["outcome"] == "beat"
    assert r["delta_reps"] == 1
    assert r["previous"]["weight_kg"] == 80.0
    assert r["previous"]["reps"] == [5, 5, 5]
    assert r["previous"]["total_reps"] == 15
    assert isinstance(r["session_id"], int)
    assert count_sessions(db_file) == 20  # 19 seed + 1


def test_log_same_call_twice_in_one_turn_is_duplicate(db_file):
    with turn("t-dup"):
        r1 = tools.log_session("rdls", 80, "kg", [5, 5, 6])
        rows = count_sessions(db_file)
        r2 = tools.log_session("rdls", 80, "kg", [5, 5, 6])
    assert r1["saved"] is True
    assert r2["saved"] is True
    assert r2["duplicate"] is True
    assert r2["session_id"] == r1["session_id"]
    assert r2["outcome"] == "beat"
    assert count_sessions(db_file) == rows == 20  # nothing written twice


def test_log_held(db_file):
    with turn("t-held"):
        r = tools.log_session("rdls", 80, "kg", [5, 5, 5])
    assert r["outcome"] == "held"
    assert r["delta_reps"] == 0
    assert r["total_reps"] == 15


def test_log_dropped(db_file):
    with turn("t-dropped"):
        r = tools.log_session("rdls", 80, "kg", [5, 5, 4])
    assert r["outcome"] == "dropped"
    assert r["delta_reps"] == -1


def test_log_825kg_is_beat_with_null_delta(db_file):
    with turn("t-heavy"):
        r = tools.log_session("rdls", 82.5, "kg", [5, 5, 5])
    assert r["outcome"] == "beat"
    assert r["delta_reps"] is None


def test_log_first_session_when_no_history(db_file):
    with turn("t-first"):
        r = tools.log_session("overhead press", 40, "kg", [5, 5])
    assert r["saved"] is True
    assert r["exercise_id"] == "overhead_press"
    assert r["outcome"] == "first"
    assert r["delta_reps"] is None
    assert r["previous"] is None
    assert r["total_reps"] == 10


def test_log_135lb_converts_to_6123kg(db_file):
    with turn("t-lb"):
        r = tools.log_session("bench press", 135, "lb", [5, 5])
    assert r["saved"] is True
    assert r["weight_kg"] == pytest.approx(61.23)
    assert r["total_reps"] == 10


# --- log_session: validation, in order, writing nothing --------------------


@pytest.mark.parametrize("exercise,weight,unit,reps,mood,code", [
    ("curls", 80, "kg", [5, 5], None, "unknown_exercise"),
    ("rdls", 80, "stone", [5, 5], None, "bad_unit"),
    ("rdls", 80, "pounds", [5, 5], None, "bad_unit"),
    ("rdls", 0, "kg", [5, 5], None, "bad_weight"),
    ("rdls", -10, "kg", [5, 5], None, "bad_weight"),
    ("rdls", 500.01, "kg", [5, 5], None, "bad_weight"),
    ("rdls", 1200, "lb", [5, 5], None, "bad_weight"),  # 544.31 kg after conversion
    ("rdls", 80, "kg", [], None, "bad_reps"),
    ("rdls", 80, "kg", [0], None, "bad_reps"),
    ("rdls", 80, "kg", [51], None, "bad_reps"),
    ("rdls", 80, "kg", [5] * 11, None, "bad_reps"),   # 11 sets
    ("rdls", 80, "kg", [5, 5], "great", "bad_mood"),
])
def test_log_validation_errors(exercise, weight, unit, reps, mood, code, db_file):
    with turn("t-val"):
        before = count_sessions(db_file)
        r = tools.log_session(exercise, weight, unit, reps, mood)
    assert r["saved"] is False
    assert r["error"] == code
    assert isinstance(r["message"], str) and r["message"]
    assert count_sessions(db_file) == before  # wrote nothing


@pytest.mark.parametrize("weight,unit,reps", [
    (500, "kg", [50]),        # upper bounds are allowed
    (0.1, "kg", [1] * 10),    # 10 sets, lowest positive weight
])
def test_log_validation_boundaries_pass(weight, unit, reps, db_file):
    with turn("t-ok"):
        r = tools.log_session("lunge", weight, unit, reps)
    assert r["saved"] is True, r


def test_log_mood_defaults_to_todays_last_non_seed_mood(db_file):
    with turn("t-mood-1"):
        r1 = tools.log_session("bench press", 60, "kg", [8, 8, 8], mood="low")
    assert r1["mood"] == "low"
    with turn("t-mood-2"):
        r2 = tools.log_session("back squat", 100, "kg", [5, 5, 5])
    assert r2["mood"] == "low"


def test_log_mood_is_null_when_nothing_saved_today(db_file):
    with turn("t-mood-none"):
        r = tools.log_session("back squat", 100, "kg", [5, 5, 5])
    assert r["mood"] is None


# --- get_last_session ------------------------------------------------------


def test_get_last_session_found():
    with turn("t-last"):
        r = tools.get_last_session("RDLs")
    assert r["found"] is True
    assert r["exercise_id"] == "romanian_deadlift"
    assert r["exercise_name"] == "Romanian deadlift"
    assert r["weight_kg"] == 80.0
    assert r["reps"] == [5, 5, 5]
    assert r["total_reps"] == 15
    assert r["mood"] == "active"
    assert isinstance(r["performed_at"], str)


def test_get_last_session_no_history():
    with turn("t-nohist"):
        r = tools.get_last_session("overhead press")
    assert r["found"] is False
    assert r["exercise_id"] == "overhead_press"
    assert r["exercise_name"] == "Overhead press"
    assert "error" not in r


def test_get_last_session_unknown_exercise():
    with turn("t-unknown"):
        r = tools.get_last_session("curls")
    assert r["found"] is False
    assert r["error"] == "unknown_exercise"
    assert isinstance(r["known"], list) and r["known"]
    assert "Romanian deadlift" in r["known"]


# --- get_mood_history -------------------------------------------------------


def test_get_mood_history_low_on_seed():
    with turn("t-moodhist"):
        r = tools.get_mood_history("low")
    assert r["mood"] == "low"
    assert r["total_sessions"] == 7
    by_ex = {e["exercise_id"]: e for e in r["by_exercise"]}
    assert by_ex["romanian_deadlift"]["exercise_name"] == "Romanian deadlift"
    assert by_ex["romanian_deadlift"]["sessions"] == 4
    assert by_ex["romanian_deadlift"]["held_or_beat"] == 3
    assert by_ex["romanian_deadlift"]["dropped"] == 1
    assert by_ex["bench_press"]["sessions"] == 3
    assert by_ex["bench_press"]["held_or_beat"] == 0
    assert by_ex["bench_press"]["dropped"] == 3
    assert r["suggested_exercise_id"] == "romanian_deadlift"
    # sorted by held_or_beat / sessions, highest first
    assert r["by_exercise"][0]["exercise_id"] == "romanian_deadlift"


def test_get_mood_history_invalid_mood():
    with turn("t-badmood"):
        r = tools.get_mood_history("great")
    assert r == {"error": "bad_mood"}


# --- trace -----------------------------------------------------------------


def test_trace_holds_one_entry_per_call():
    with turn("t-trace") as trace:
        tools.get_last_session("rdls")
        tools.log_session("rdls", 80, "kg", [5, 5, 6])
        tools.get_last_session("curls")
    assert len(trace) == 3
    assert [e["tool"] for e in trace] == ["get_last_session", "log_session", "get_last_session"]
    for e in trace:
        assert set(e) >= {"tool", "args", "result", "ms"}
        assert isinstance(e["ms"], (int, float)) and e["ms"] >= 0
    assert trace[0]["args"] == {"exercise": "rdls"}
    assert trace[1]["result"]["saved"] is True
    assert trace[1]["result"]["outcome"] == "beat"
    assert trace[2]["result"]["error"] == "unknown_exercise"
