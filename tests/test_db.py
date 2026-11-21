"""Contract tests for Task 1: app/db.py and app/vocab.py.

Written from docs/BUILD-BRIEF.md before the code exists. Every test skips
while app/db.py or app/vocab.py is not merged (at run time, so pytest still
collects the tests and exits 0), so main always passes.

Interface assumed from the brief (Task 1 implements to this):

- vocab.EXERCISES: list of {"id": str, "name": str, "aliases": [str, ...]}
- vocab.context_bias_terms() -> list[str]
- db.DB_PATH: path of the sqlite file (voicefit.db)
- db.reset_db(path=None) -> (re)create schema + seed; path defaults to the
  current db.DB_PATH at call time
- db.resolve_exercise(text, path=None) -> exercise id, or None if unknown

The schema and the 19 seed rows are asserted with raw SQL exactly as
specified in the brief.
"""
import json
import sqlite3
from datetime import datetime, timezone

import pytest

try:
    import app.db as db
    import app.vocab as vocab
    _IMPORT_ERROR = None
except ImportError as exc:
    # Skip at run time, not at collection: a module-level skip leaves pytest
    # with zero collected items and exit code 5, and main must always pass.
    db = vocab = None
    _IMPORT_ERROR = exc


@pytest.fixture(autouse=True)
def _skip_while_module_missing():
    if _IMPORT_ERROR is not None:
        pytest.skip(f"app/db.py or app/vocab.py not merged yet: {_IMPORT_ERROR}")

# The exercises table from the brief: id -> (name, aliases)
EXPECTED_EXERCISES = {
    "romanian_deadlift": ("Romanian deadlift",
                          {"rdl", "rdls", "romanian deadlift", "romanian deadlifts"}),
    "bench_press": ("Bench press", {"bench", "bench press"}),
    "back_squat": ("Back squat", {"squat", "squats", "back squat"}),
    "overhead_press": ("Overhead press",
                       {"ohp", "overhead press", "shoulder press"}),
    "deadlift": ("Deadlift", {"deadlift", "deadlifts"}),
    "barbell_row": ("Barbell row",
                    {"row", "rows", "barbell row", "bent over row"}),
    "pull_up": ("Pull-up", {"pull up", "pull ups", "pullups", "chin ups"}),
    "lunge": ("Lunge", {"lunge", "lunges"}),
}

# The seed rows from the brief: (exercise, days ago, kg, reps, mood)
EXPECTED_SEED = [
    ("romanian_deadlift", 28, 75, [5, 5, 5], "active"),
    ("romanian_deadlift", 24, 75, [5, 5, 5], "low"),
    ("romanian_deadlift", 21, 77.5, [5, 5, 5], "pumped"),
    ("romanian_deadlift", 17, 77.5, [5, 5, 5], "low"),
    ("romanian_deadlift", 14, 80, [5, 5, 4], "active"),
    ("romanian_deadlift", 10, 80, [5, 5, 5], "low"),
    ("romanian_deadlift", 7, 80, [5, 4, 4], "low"),
    ("romanian_deadlift", 3, 80, [5, 5, 5], "active"),
    ("bench_press", 27, 60, [8, 8, 8], "active"),
    ("bench_press", 23, 60, [8, 7, 6], "low"),
    ("bench_press", 20, 60, [8, 8, 8], "pumped"),
    ("bench_press", 16, 62.5, [8, 8, 7], "active"),
    ("bench_press", 13, 62.5, [7, 6, 6], "low"),
    ("bench_press", 9, 62.5, [8, 8, 8], "pumped"),
    ("bench_press", 6, 62.5, [8, 7, 6], "low"),
    ("bench_press", 2, 62.5, [8, 8, 8], "active"),
    ("back_squat", 26, 100, [5, 5, 5], "active"),
    ("back_squat", 12, 100, [5, 5, 5], "pumped"),
    ("back_squat", 5, 102.5, [5, 5, 5], "active"),
]

NO_HISTORY_EXERCISES = ["overhead_press", "deadlift", "barbell_row", "pull_up", "lunge"]


def parse_iso(s):
    """Parse an ISO 8601 UTC timestamp like 2026-11-18T10:00:00Z."""
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# --- vocab.py -----------------------------------------------------------


def test_exercises_match_the_brief():
    got = {e["id"]: e for e in vocab.EXERCISES}
    assert set(got) == set(EXPECTED_EXERCISES)
    for ex_id, (name, aliases) in EXPECTED_EXERCISES.items():
        assert got[ex_id]["name"] == name
        assert set(got[ex_id]["aliases"]) == aliases


def test_context_bias_terms():
    terms = set(vocab.context_bias_terms())
    expected = {"reps", "sets", "kilos", "kg", "pounds"}
    for name, aliases in EXPECTED_EXERCISES.values():
        expected.add(name)
        expected |= aliases
    assert terms == expected


# --- alias resolution ----------------------------------------------------


@pytest.mark.parametrize("text,expected", [
    ("RDLs", "romanian_deadlift"),
    ("rdl", "romanian_deadlift"),
    ("RDL", "romanian_deadlift"),
    ("Romanian Deadlift", "romanian_deadlift"),
    ("romanian deadlifts", "romanian_deadlift"),
    ("Bench", "bench_press"),
    ("bench press", "bench_press"),
    ("SQUAT", "back_squat"),
    ("back squat", "back_squat"),
    ("OHP", "overhead_press"),
    ("shoulder press", "overhead_press"),
    ("deadlift", "deadlift"),          # exact alias, not a substring match
    ("Deadlifts", "deadlift"),
    ("row", "barbell_row"),
    ("Bent Over Row", "barbell_row"),
    ("chin ups", "pull_up"),
    ("PULLUPS", "pull_up"),
    ("Lunges", "lunge"),
    ("romanian_deadlift", "romanian_deadlift"),  # id resolves too
])
def test_resolve_exercise(text, expected):
    assert db.resolve_exercise(text) == expected


@pytest.mark.parametrize("text", ["curls", "", "romanian", "press", "unknown lift", "  "])
def test_resolve_exercise_unknown_returns_none(text):
    assert db.resolve_exercise(text) is None


# --- schema and seed ------------------------------------------------------


def test_seed_row_count_is_19(sql):
    assert sql.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 19
    assert sql.execute("SELECT COUNT(*) FROM exercises").fetchone()[0] == 8
    assert sql.execute("SELECT COUNT(*) FROM sessions WHERE is_seed = 1").fetchone()[0] == 19


def test_seed_rows_match_the_brief(sql):
    now = datetime.now(timezone.utc)
    rows = sql.execute(
        "SELECT exercise_id, performed_at, weight_kg, reps, mood, is_seed FROM sessions"
    ).fetchall()
    assert len(rows) == len(EXPECTED_SEED)
    got = []
    for r in rows:
        performed = parse_iso(r["performed_at"])
        days_ago = (now - performed).total_seconds() / 86400
        got.append((r["exercise_id"], days_ago, r["weight_kg"],
                    json.loads(r["reps"]), r["mood"], r["is_seed"]))
    for ex_id, days, kg, reps, mood in EXPECTED_SEED:
        matches = [g for g in got
                   if g[0] == ex_id and abs(g[1] - days) < 1 / 1440
                   and g[2] == kg and g[3] == reps and g[4] == mood and g[5] == 1]
        assert matches, f"missing seed row: {ex_id} {days}d {kg}kg {reps} {mood}"


def test_performed_at_is_iso8601_utc(sql):
    for r in sql.execute("SELECT performed_at FROM sessions"):
        dt = parse_iso(r["performed_at"])
        assert dt.tzinfo is not None


def test_last_romanian_deadlift_is_80kg_555(sql):
    r = sql.execute(
        "SELECT weight_kg, reps, mood, performed_at FROM sessions"
        " WHERE exercise_id = 'romanian_deadlift'"
        " ORDER BY performed_at DESC, id DESC LIMIT 1"
    ).fetchone()
    assert r["weight_kg"] == 80.0
    assert json.loads(r["reps"]) == [5, 5, 5]
    assert r["mood"] == "active"
    days_ago = (datetime.now(timezone.utc) - parse_iso(r["performed_at"])).total_seconds() / 86400
    assert abs(days_ago - 3) < 1 / 1440


def test_exercises_without_history(sql):
    for ex_id in NO_HISTORY_EXERCISES:
        n = sql.execute(
            "SELECT COUNT(*) FROM sessions WHERE exercise_id = ?", (ex_id,)
        ).fetchone()[0]
        assert n == 0, ex_id


def test_unique_turn_id_exercise_id(sql):
    # UNIQUE (turn_id, exercise_id): a retried tool call cannot save twice.
    sql.execute(
        "INSERT INTO sessions (exercise_id, performed_at, weight_kg, reps, mood, turn_id, is_seed)"
        " VALUES ('lunge', '2026-11-21T10:00:00Z', 20, '[5]', NULL, 'turn-x', 0)"
    )
    sql.commit()
    with pytest.raises(sqlite3.IntegrityError):
        sql.execute(
            "INSERT INTO sessions (exercise_id, performed_at, weight_kg, reps, mood, turn_id, is_seed)"
            " VALUES ('lunge', '2026-11-21T11:00:00Z', 20, '[5]', NULL, 'turn-x', 0)"
        )
    sql.rollback()


def test_reset_restores_seed_after_extra_rows(sql, db_file):
    sql.execute(
        "INSERT INTO sessions (exercise_id, performed_at, weight_kg, reps, mood, turn_id, is_seed)"
        " VALUES ('lunge', '2026-11-21T10:00:00Z', 20, '[5,5]', 'low', 'turn-extra', 0)"
    )
    sql.commit()
    assert sql.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 20

    db.reset_db()

    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 19
    assert conn.execute(
        "SELECT COUNT(*) FROM sessions WHERE turn_id = 'turn-extra'"
    ).fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM sessions WHERE is_seed = 1").fetchone()[0] == 19
    r = conn.execute(
        "SELECT weight_kg, reps FROM sessions WHERE exercise_id = 'romanian_deadlift'"
        " ORDER BY performed_at DESC, id DESC LIMIT 1"
    ).fetchone()
    assert r["weight_kg"] == 80.0
    assert json.loads(r["reps"]) == [5, 5, 5]
    conn.close()
