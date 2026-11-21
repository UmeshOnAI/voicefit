"""SQLite storage for VoiceFit: schema, seed, reset, and the queries tools.py needs.

Task 1 owns this file. Every public function takes an optional ``path`` that
defaults to the *current* ``DB_PATH`` at call time, so tests can point the app
at a temporary file (see tests/conftest.py).

Timestamps are ISO 8601 UTC strings ("2026-11-18T10:00:00Z"); reps are stored
as a JSON list of ints. All arithmetic on weights/reps lives in tools.py.
"""

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import vocab

DB_PATH = Path(__file__).resolve().parent.parent / "voicefit.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS exercises (
  id      TEXT PRIMARY KEY,
  name    TEXT NOT NULL,
  aliases TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  exercise_id    TEXT NOT NULL REFERENCES exercises(id),
  performed_at   TEXT NOT NULL,
  weight_kg      REAL NOT NULL,
  reps           TEXT NOT NULL,
  mood           TEXT,
  raw_transcript TEXT,
  turn_id        TEXT,
  is_seed        INTEGER NOT NULL DEFAULT 0,
  UNIQUE (turn_id, exercise_id)
);
"""

# (exercise_id, days_ago, weight_kg, reps, mood) — performed_at = now - days_ago.
SEED_SESSIONS = [
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


def _path(path) -> Path:
    # Read DB_PATH at call time so tests can monkeypatch it.
    return Path(path) if path is not None else Path(DB_PATH)


def _conn(path) -> sqlite3.Connection:
    conn = sqlite3.connect(_path(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def utcnow() -> str:
    return iso_utc(datetime.now(timezone.utc))


def today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _row_to_session(r: sqlite3.Row) -> dict:
    return {
        "id": r["id"],
        "exercise_id": r["exercise_id"],
        "performed_at": r["performed_at"],
        "weight_kg": r["weight_kg"],
        "reps": json.loads(r["reps"]),
        "mood": r["mood"],
        "raw_transcript": r["raw_transcript"],
        "turn_id": r["turn_id"],
        "is_seed": bool(r["is_seed"]),
    }


def _seed_sessions(conn: sqlite3.Connection) -> None:
    now = datetime.now(timezone.utc)
    rows = [
        (ex_id, iso_utc(now - timedelta(days=days)), float(kg), json.dumps(reps), mood, 1)
        for ex_id, days, kg, reps, mood in SEED_SESSIONS
    ]
    conn.executemany(
        "INSERT INTO sessions (exercise_id, performed_at, weight_kg, reps, mood, is_seed)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )


def _ensure_exercises(conn: sqlite3.Connection) -> None:
    conn.executemany(
        "INSERT OR IGNORE INTO exercises (id, name, aliases) VALUES (?, ?, ?)",
        [(e["id"], e["name"], json.dumps(e["aliases"])) for e in vocab.EXERCISES],
    )


def reset_db(path=None) -> None:
    """(Re)create the schema and the seed with fresh dates; deletes all rows."""
    with closing(_conn(path)) as conn:
        _ensure_schema(conn)
        conn.execute("DELETE FROM sessions")
        conn.execute("DELETE FROM exercises")
        _ensure_exercises(conn)
        _seed_sessions(conn)
        conn.commit()


def init_db(path=None) -> None:
    """Create the schema if needed and seed only when the db is empty."""
    with closing(_conn(path)) as conn:
        _ensure_schema(conn)
        _ensure_exercises(conn)
        if conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0:
            _seed_sessions(conn)
        conn.commit()


# --- exercises and alias resolution ---------------------------------------


def list_exercises(path=None) -> list[dict]:
    """All exercises as [{"id", "name"}], ordered by name."""
    with closing(_conn(path)) as conn:
        _ensure_schema(conn)
        rows = conn.execute("SELECT id, name FROM exercises ORDER BY name").fetchall()
    return [{"id": r["id"], "name": r["name"]} for r in rows]


def get_exercise(exercise_id: str, path=None) -> dict | None:
    """One exercise as {"id", "name", "aliases"} (aliases parsed), or None."""
    with closing(_conn(path)) as conn:
        _ensure_schema(conn)
        r = conn.execute(
            "SELECT id, name, aliases FROM exercises WHERE id = ?", (exercise_id,)
        ).fetchone()
    if not r:
        return None
    return {"id": r["id"], "name": r["name"], "aliases": json.loads(r["aliases"])}


def resolve_exercise(text, path=None) -> str | None:
    """Resolve a spoken/written exercise to its id via id, name or alias.

    Case-insensitive exact match only ("press" does not resolve). None if unknown.
    """
    if text is None:
        return None
    term = str(text).strip().lower()
    if not term:
        return None
    with closing(_conn(path)) as conn:
        _ensure_schema(conn)
        rows = conn.execute("SELECT id, name, aliases FROM exercises").fetchall()
    for r in rows:
        aliases = [a.lower() for a in json.loads(r["aliases"])]
        if term in (r["id"].lower(), r["name"].lower(), *aliases):
            return r["id"]
    return None


# --- session queries --------------------------------------------------------


def get_last_session(exercise_id: str, path=None) -> dict | None:
    """The newest session of the exercise, or None."""
    with closing(_conn(path)) as conn:
        _ensure_schema(conn)
        r = conn.execute(
            "SELECT * FROM sessions WHERE exercise_id = ?"
            " ORDER BY performed_at DESC, id DESC LIMIT 1",
            (exercise_id,),
        ).fetchone()
    return _row_to_session(r) if r else None


def get_previous_session(exercise_id: str, performed_at: str, session_id: int, path=None) -> dict | None:
    """The session of the exercise immediately before the given one, or None."""
    with closing(_conn(path)) as conn:
        _ensure_schema(conn)
        r = conn.execute(
            "SELECT * FROM sessions WHERE exercise_id = ?"
            " AND (performed_at < ? OR (performed_at = ? AND id < ?))"
            " ORDER BY performed_at DESC, id DESC LIMIT 1",
            (exercise_id, performed_at, performed_at, session_id),
        ).fetchone()
    return _row_to_session(r) if r else None


def list_sessions(exercise_id: str | None = None, limit: int | None = None, path=None) -> list[dict]:
    """Sessions, newest first; optionally one exercise only, optionally limited."""
    sql = "SELECT * FROM sessions"
    params: list = []
    if exercise_id is not None:
        sql += " WHERE exercise_id = ?"
        params.append(exercise_id)
    sql += " ORDER BY performed_at DESC, id DESC"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    with closing(_conn(path)) as conn:
        _ensure_schema(conn)
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_session(r) for r in rows]


def sessions_with_mood(mood: str, path=None) -> list[dict]:
    """All sessions with the given mood, oldest first."""
    with closing(_conn(path)) as conn:
        _ensure_schema(conn)
        rows = conn.execute(
            "SELECT * FROM sessions WHERE mood = ? ORDER BY performed_at, id", (mood,)
        ).fetchall()
    return [_row_to_session(r) for r in rows]


def latest_non_seed_today(path=None) -> dict | None:
    """The newest non-seed session performed today (UTC), for mood inheritance."""
    with closing(_conn(path)) as conn:
        _ensure_schema(conn)
        r = conn.execute(
            "SELECT * FROM sessions WHERE is_seed = 0 AND substr(performed_at, 1, 10) = ?"
            " ORDER BY performed_at DESC, id DESC LIMIT 1",
            (today_utc(),),
        ).fetchone()
    return _row_to_session(r) if r else None


def get_session_by_turn_exercise(turn_id: str, exercise_id: str, path=None) -> dict | None:
    with closing(_conn(path)) as conn:
        _ensure_schema(conn)
        r = conn.execute(
            "SELECT * FROM sessions WHERE turn_id = ? AND exercise_id = ?",
            (turn_id, exercise_id),
        ).fetchone()
    return _row_to_session(r) if r else None


def insert_session(
    exercise_id: str,
    weight_kg: float,
    reps: list[int],
    mood: str | None = None,
    raw_transcript: str | None = None,
    turn_id: str | None = None,
    performed_at: str | None = None,
    is_seed: int = 0,
    path=None,
) -> tuple[dict, bool]:
    """Insert a session. Returns (session, created).

    UNIQUE (turn_id, exercise_id) makes a retried call a no-op: on conflict the
    existing row is returned with created=False and nothing is written.
    """
    with closing(_conn(path)) as conn:
        _ensure_schema(conn)
        try:
            cur = conn.execute(
                "INSERT INTO sessions (exercise_id, performed_at, weight_kg, reps, mood,"
                " raw_transcript, turn_id, is_seed) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    exercise_id,
                    performed_at or utcnow(),
                    float(weight_kg),
                    json.dumps(list(reps)),
                    mood,
                    raw_transcript,
                    turn_id,
                    int(is_seed),
                ),
            )
            conn.commit()
            new_id = cur.lastrowid
        except sqlite3.IntegrityError:
            conn.rollback()
            r = conn.execute(
                "SELECT * FROM sessions WHERE turn_id = ? AND exercise_id = ?",
                (turn_id, exercise_id),
            ).fetchone()
            return _row_to_session(r), False
        r = conn.execute("SELECT * FROM sessions WHERE id = ?", (new_id,)).fetchone()
        return _row_to_session(r), True


# --- mutations used by the API ----------------------------------------------


def set_mood_today(mood: str, path=None) -> int:
    """Set mood on all non-seed sessions performed today (UTC). Returns rows updated."""
    with closing(_conn(path)) as conn:
        _ensure_schema(conn)
        cur = conn.execute(
            "UPDATE sessions SET mood = ? WHERE is_seed = 0 AND substr(performed_at, 1, 10) = ?",
            (mood, today_utc()),
        )
        conn.commit()
        return cur.rowcount


def delete_non_seed(path=None) -> int:
    """Delete all non-seed sessions. Returns rows deleted."""
    with closing(_conn(path)) as conn:
        _ensure_schema(conn)
        cur = conn.execute("DELETE FROM sessions WHERE is_seed = 0")
        conn.commit()
        return cur.rowcount


def count_sessions(path=None) -> int:
    with closing(_conn(path)) as conn:
        _ensure_schema(conn)
        return conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
