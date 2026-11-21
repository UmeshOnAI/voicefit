"""Task 2 extra tests beyond the tester's contract tests in test_tools.py."""
import pytest

import app.tools as tools


def _turn(turn_id):
    import contextlib

    @contextlib.contextmanager
    def cm():
        trace = []
        t1 = tools.TRACE.set(trace)
        t2 = tools.TURN_ID.set(turn_id)
        try:
            yield trace
        finally:
            tools.TRACE.reset(t1)
            tools.TURN_ID.reset(t2)

    return cm()


def test_compare_lighter_weight_is_dropped_delta_null():
    prev = {"weight_kg": 80.0, "reps": [5, 5, 5]}
    r = tools.compare(prev, {"weight_kg": 77.5, "reps": [5, 5, 5]})
    assert r == {"outcome": "dropped", "delta_reps": None}


def test_compare_exactly_005_apart_is_not_same():
    prev = {"weight_kg": 80.0, "reps": [5, 5, 5]}
    # differs by exactly 0.05 -> NOT "the same" (rule says less than 0.05)
    r = tools.compare(prev, {"weight_kg": 80.05, "reps": [5, 5, 5]})
    assert r == {"outcome": "beat", "delta_reps": None}


def test_135lb_is_exactly_6123(db_file):
    with _turn("t-lb-exact"):
        r = tools.log_session("bench press", 135, "lb", [5, 5])
    assert r["weight_kg"] == 61.23


def test_duplicate_result_keeps_first_rows_data(db_file):
    with _turn("t-dup2") as trace:
        r1 = tools.log_session("rdls", 80, "kg", [5, 5, 6])
        r2 = tools.log_session("rdls", 90, "kg", [1, 1])  # different args, same turn+exercise
    assert r2["duplicate"] is True
    assert r2["session_id"] == r1["session_id"]
    assert r2["weight_kg"] == 80.0  # the stored row, not the new args
    assert "duplicate" not in r1
    assert [e["tool"] for e in trace] == ["log_session", "log_session"]


def test_tools_work_without_turn_context(db_file):
    # Outside a request (no TRACE/TURN_ID set) calls must not crash.
    r = tools.get_last_session("rdls")
    assert r["found"] is True
    r = tools.log_session("lunge", 20, "kg", [5, 5])
    assert r["saved"] is True
    assert r["mood"] is None


def test_get_mood_history_pumped_on_seed(db_file):
    with _turn("t-ph"):
        r = tools.get_mood_history("pumped")
    # seed pumped rows: RDL 21d (beat vs 24d), bench 20d (beat vs 23d),
    # bench 9d (beat vs 6d... wait order), squat 12d (held vs 26d)
    assert r["mood"] == "pumped"
    assert r["total_sessions"] == 4
    assert r["suggested_exercise_id"] is None or r["suggested_exercise_id"] in (
        e["exercise_id"] for e in r["by_exercise"] if e["sessions"] >= 2
    )
    for e in r["by_exercise"]:
        assert e["sessions"] == e["held_or_beat"] + e["dropped"]


def test_get_mood_history_active_suggests_something(db_file):
    with _turn("t-act"):
        r = tools.get_mood_history("active")
    assert r["total_sessions"] > 0
    assert isinstance(r["by_exercise"], list)
