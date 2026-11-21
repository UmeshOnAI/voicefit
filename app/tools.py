"""Pure tool logic + trace for VoiceFit (Task 2).

Plain functions taking and returning JSON-serialisable values. No Mistral
imports here. Every call appends {"tool", "args", "result", "ms"} to the
current request's trace (the TRACE context var, a list set per /api/turn by
main.py); log_session reads the current turn_id from the TURN_ID context var.

All arithmetic (totals, comparisons, counts) lives here, never in the model.
"""

import time
from contextvars import ContextVar

from . import db
from .vocab import MOODS

TRACE: ContextVar = ContextVar("voicefit_trace", default=None)
TURN_ID: ContextVar = ContextVar("voicefit_turn_id", default=None)

LB_TO_KG = 0.45359237
SAME_WEIGHT_TOLERANCE_KG = 0.05  # weights differ by less than this -> "the same"
MAX_WEIGHT_KG = 500
MIN_SETS, MAX_SETS = 1, 10
MIN_REP, MAX_REP = 1, 50


def _record(tool: str, args: dict, result: dict, started: float) -> None:
    ms = round((time.perf_counter() - started) * 1000, 3)
    trace = TRACE.get()
    if trace is not None:
        trace.append({"tool": tool, "args": args, "result": result, "ms": ms})


def total_reps(reps: list[int]) -> int:
    return sum(reps)


def compare(previous: dict | None, new: dict) -> dict:
    """Compare a session with the immediately preceding session of the exercise.

    previous/new are dicts with "weight_kg" and "reps"; previous may be None.
    Returns {"outcome": first|beat|held|dropped, "delta_reps": int|None}.
    delta_reps is null unless the weights are the same (< 0.05 kg apart).
    """
    if previous is None:
        return {"outcome": "first", "delta_reps": None}
    pw, nw = previous["weight_kg"], new["weight_kg"]
    # Compare in integer hundredths of a kg: stored weights are 2-decimal values,
    # and "less than 0.05 kg apart" must hold exactly at the 0.05 boundary.
    same_weight = abs(round(nw * 100) - round(pw * 100)) < SAME_WEIGHT_TOLERANCE_KG * 100
    if not same_weight:
        if nw > pw:
            return {"outcome": "beat", "delta_reps": None}
        return {"outcome": "dropped", "delta_reps": None}
    delta = total_reps(new["reps"]) - total_reps(previous["reps"])
    if delta > 0:
        outcome = "beat"
    elif delta == 0:
        outcome = "held"
    else:
        outcome = "dropped"
    return {"outcome": outcome, "delta_reps": delta}


def _fail(code: str, message: str) -> dict:
    return {"saved": False, "error": code, "message": message}


def get_last_session(exercise: str) -> dict:
    """Resolve the exercise and return its newest session (or found: false)."""
    started = time.perf_counter()
    ex_id = db.resolve_exercise(exercise)
    if ex_id is None:
        result = {
            "found": False,
            "error": "unknown_exercise",
            "known": [e["name"] for e in db.list_exercises()],
        }
    else:
        ex = db.get_exercise(ex_id)
        session = db.get_last_session(ex_id)
        if session is None:
            result = {"found": False, "exercise_id": ex_id, "exercise_name": ex["name"]}
        else:
            result = {
                "found": True,
                "exercise_id": ex_id,
                "exercise_name": ex["name"],
                "performed_at": session["performed_at"],
                "weight_kg": session["weight_kg"],
                "reps": session["reps"],
                "total_reps": total_reps(session["reps"]),
                "mood": session["mood"],
            }
    _record("get_last_session", {"exercise": exercise}, result, started)
    return result


def _saved_result(ex: dict, row: dict, previous: dict | None, duplicate: bool) -> dict:
    cmp = compare(previous, row)
    result = {
        "saved": True,
        "session_id": row["id"],
        "exercise_id": ex["id"],
        "exercise_name": ex["name"],
        "weight_kg": row["weight_kg"],
        "reps": row["reps"],
        "total_reps": total_reps(row["reps"]),
        "mood": row["mood"],
        "previous": (
            {
                "performed_at": previous["performed_at"],
                "weight_kg": previous["weight_kg"],
                "reps": previous["reps"],
                "total_reps": total_reps(previous["reps"]),
            }
            if previous is not None
            else None
        ),
        "outcome": cmp["outcome"],
        "delta_reps": cmp["delta_reps"],
    }
    if duplicate:
        result["duplicate"] = True
    return result


def log_session(exercise: str, weight: float, unit: str, reps: list[int], mood: str | None = None) -> dict:
    """Validate and save one session. Validation order: exercise, unit, weight, reps, mood."""
    started = time.perf_counter()
    args = {"exercise": exercise, "weight": weight, "unit": unit, "reps": reps, "mood": mood}

    ex_id = db.resolve_exercise(exercise)
    if ex_id is None:
        result = _fail("unknown_exercise", f"I don't know an exercise called {exercise!r}.")
        _record("log_session", args, result, started)
        return result
    ex = db.get_exercise(ex_id)

    unit_norm = str(unit).strip().lower() if unit is not None else ""
    if unit_norm not in ("kg", "lb"):
        result = _fail("bad_unit", "The unit must be kg or lb.")
        _record("log_session", args, result, started)
        return result

    try:
        weight_num = float(weight)
    except (TypeError, ValueError):
        weight_num = 0.0
    kg = weight_num if unit_norm == "kg" else round(weight_num * LB_TO_KG, 2)
    if not (0 < kg <= MAX_WEIGHT_KG):
        result = _fail("bad_weight", f"Weight must be above 0 and at most {MAX_WEIGHT_KG} kg.")
        _record("log_session", args, result, started)
        return result

    if (
        not isinstance(reps, list)
        or not (MIN_SETS <= len(reps) <= MAX_SETS)
        or not all(isinstance(r, int) and not isinstance(r, bool) and MIN_REP <= r <= MAX_REP for r in reps)
    ):
        result = _fail("bad_reps", f"Reps must be {MIN_SETS} to {MAX_SETS} sets of {MIN_REP} to {MAX_REP} reps each.")
        _record("log_session", args, result, started)
        return result

    if mood is not None and mood not in MOODS:
        result = _fail("bad_mood", "Mood must be one of: low, active, pumped.")
        _record("log_session", args, result, started)
        return result

    if mood is None:
        today = db.latest_non_seed_today()
        mood = today["mood"] if today else None

    turn_id = TURN_ID.get()

    # A retried tool call in the same turn must not save twice.
    if turn_id is not None:
        existing = db.get_session_by_turn_exercise(turn_id, ex_id)
        if existing is not None:
            previous = db.get_previous_session(ex_id, existing["performed_at"], existing["id"])
            result = _saved_result(ex, existing, previous, duplicate=True)
            _record("log_session", args, result, started)
            return result

    previous = db.get_last_session(ex_id)
    row, _created = db.insert_session(
        ex_id, kg, list(reps), mood=mood, turn_id=turn_id
    )
    result = _saved_result(ex, row, previous, duplicate=False)
    _record("log_session", args, result, started)
    return result


def get_mood_history(mood: str) -> dict:
    """Outcomes of every session with this mood that has a previous session."""
    started = time.perf_counter()
    args = {"mood": mood}
    if mood not in MOODS:
        result = {"error": "bad_mood"}
        _record("get_mood_history", args, result, started)
        return result

    names = {e["id"]: e["name"] for e in db.list_exercises()}
    by_exercise: dict[str, dict] = {}
    total = 0
    for s in db.sessions_with_mood(mood):
        previous = db.get_previous_session(s["exercise_id"], s["performed_at"], s["id"])
        if previous is None:
            continue
        total += 1
        cmp = compare(previous, s)
        entry = by_exercise.setdefault(
            s["exercise_id"],
            {
                "exercise_id": s["exercise_id"],
                "exercise_name": names.get(s["exercise_id"], s["exercise_id"]),
                "sessions": 0,
                "held_or_beat": 0,
                "dropped": 0,
            },
        )
        entry["sessions"] += 1
        if cmp["outcome"] in ("held", "beat"):
            entry["held_or_beat"] += 1
        elif cmp["outcome"] == "dropped":
            entry["dropped"] += 1

    ordered = sorted(
        by_exercise.values(),
        key=lambda e: (-(e["held_or_beat"] / e["sessions"]), -e["sessions"], e["exercise_id"]),
    )
    suggested = next((e["exercise_id"] for e in ordered if e["sessions"] >= 2), None)
    result = {
        "mood": mood,
        "total_sessions": total,
        "by_exercise": ordered,
        "suggested_exercise_id": suggested,
    }
    _record("get_mood_history", args, result, started)
    return result
