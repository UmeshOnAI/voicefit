"""Tests for the Task 5 /api/turn response assembly and the plain routes.

Calls the route functions directly (no HTTP client needed); the live
end-to-end checks against a running uvicorn are in the Task 5 PR body.
"""

import asyncio

import pytest
from fastapi import HTTPException

from app import db
from app import main


def run(coro):
    return asyncio.run(coro)


# --- tone / mood choice (computed in code, never by the model) -------------


def test_choose_tone_beat_wins_over_mood():
    assert main.choose_tone([{"outcome": "beat"}], "low") == "pleased"
    assert main.choose_tone([{"outcome": "held"}, {"outcome": "beat"}], None) == "pleased"


def test_choose_tone_calm_then_neutral():
    assert main.choose_tone([{"outcome": "held"}], "low") == "calm"
    assert main.choose_tone([], "low") == "calm"
    assert main.choose_tone([{"outcome": "dropped"}], "active") == "neutral"
    assert main.choose_tone([], None) == "neutral"


def test_turn_mood_prefers_saved_session_mood():
    trace = [{"tool": "get_mood_history", "args": {"mood": "low"}, "result": {}, "ms": 1}]
    assert main.turn_mood(trace, [{"mood": "pumped"}]) == "pumped"


def test_turn_mood_falls_back_to_mood_history_then_none():
    trace = [{"tool": "get_mood_history", "args": {"mood": "low"}, "result": {}, "ms": 1}]
    assert main.turn_mood(trace, []) == "low"
    assert main.turn_mood(trace, [{"mood": None}]) == "low"
    assert main.turn_mood([], []) is None


# --- plain routes -----------------------------------------------------------


def test_sessions_route_newest_first_with_total_and_seed(fresh_db):
    rows = run(main.get_sessions("romanian_deadlift", 4))
    assert len(rows) == 4
    assert rows[0]["weight_kg"] == 80.0
    assert rows[0]["reps"] == [5, 5, 5]
    assert rows[0]["total_reps"] == 15
    assert rows[0]["is_seed"] is True


def test_sessions_route_unknown_exercise_returns_empty(fresh_db):
    assert run(main.get_sessions("curls", 5)) == []


def test_exercises_route(fresh_db):
    exs = run(main.get_exercises())
    assert len(exs) == 8
    assert {"id": "romanian_deadlift", "name": "Romanian deadlift"} in exs


def test_mood_route_sets_today_and_rejects_bad_mood(fresh_db):
    db.insert_session("bench_press", 60, [8, 8, 8])
    assert run(main.post_mood(main.MoodIn(mood="low"))) == {"mood": "low", "updated": 1}
    assert db.latest_non_seed_today()["mood"] == "low"
    with pytest.raises(HTTPException) as err:
        run(main.post_mood(main.MoodIn(mood="grumpy")))
    assert err.value.status_code == 400


def test_reset_route_restores_seed_and_drops_agent_sessions(fresh_db):
    db.insert_session("bench_press", 60, [8, 8, 8])
    out = run(main.post_reset())
    assert out["reset"] is True
    assert db.count_sessions() == 19  # seed only, fresh dates
    from app import agent
    agent._active_sessions.add("stale-session-id")
    assert run(main.post_reset())["dropped_agent_sessions"] == 1
    assert "stale-session-id" not in agent._active_sessions


def test_turn_requires_exactly_one_of_audio_or_transcript(fresh_db):
    with pytest.raises(HTTPException) as err:
        run(main.post_turn(None, None, None))
    assert err.value.status_code == 400
    with pytest.raises(HTTPException) as err:
        run(main.post_turn(object(), "rdls 80kg 5 5 5", None))
    assert err.value.status_code == 400


def test_index_serves_static_page():
    resp = run(main.index())
    assert resp.path.name == "index.html"
