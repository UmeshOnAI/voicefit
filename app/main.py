"""FastAPI app for VoiceFit (Task 5): POST /api/turn plus the other routes.

/api/turn wires the pipeline: voice.transcribe (audio path only) ->
agent.run_turn -> tools (traced via the TRACE/TURN_ID context vars) -> tone
chosen in code -> voice.speak. Speech failure never fails the request.

Routes per docs/BUILD-BRIEF.md:
  POST /api/turn                 multipart: audio XOR transcript, session_id
  GET  /api/sessions?exercise=&limit=5   newest first, with total_reps, is_seed
  GET  /api/exercises            id and name list
  POST /api/mood                 {"mood": "low"} -> non-seed sessions of today
  POST /api/reset                delete non-seed, reseed with fresh dates, drop
                                 agent sessions
  GET  /                         static/index.html
"""

import asyncio
import base64
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import agent as agent_module
from . import db
from . import tools
from . import voice
from .vocab import MOODS

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    try:
        # Also exports MISTRAL_API_KEY into the environment for the agents SDK.
        voice.load_api_key()
    except RuntimeError:
        pass  # no key configured: /api/turn fails per request, the rest works
    yield


app = FastAPI(title="VoiceFit", lifespan=lifespan)


def choose_tone(saved_sessions: list[dict], mood: str | None) -> str:
    """Tone is chosen in code: pleased if any saved session beat, else calm if
    the mood is low, else neutral."""
    if any(s.get("outcome") == "beat" for s in saved_sessions):
        return "pleased"
    if mood == "low":
        return "calm"
    return "neutral"


def turn_mood(trace: list[dict], saved_sessions: list[dict]) -> str | None:
    """The mood on the sessions saved this turn, else the mood passed to
    get_mood_history this turn, else None."""
    for s in saved_sessions:
        if s.get("mood"):
            return s["mood"]
    for entry in reversed(trace):
        if entry.get("tool") == "get_mood_history":
            return (entry.get("args") or {}).get("mood")
    return None


@app.post("/api/turn")
async def post_turn(
    audio: UploadFile | None = File(default=None),
    transcript: str | None = Form(default=None),
    session_id: str | None = Form(default=None),
) -> dict:
    has_audio = audio is not None
    has_text = transcript is not None and transcript.strip() != ""
    if has_audio == has_text:
        raise HTTPException(status_code=400, detail="exactly one of audio or transcript is required")

    turn_id = uuid.uuid4().hex
    trace: list[dict] = []
    trace_token = tools.TRACE.set(trace)
    turn_token = tools.TURN_ID.set(turn_id)
    try:
        if has_audio:
            audio_bytes = await audio.read()
            if not audio_bytes:
                raise HTTPException(status_code=400, detail="empty audio upload")
            text = await asyncio.to_thread(voice.transcribe, audio_bytes, audio.filename or "clip.webm")
        else:
            text = transcript.strip()

        reply_text, new_session_id = await agent_module.run_turn(
            text, session_id, turn_id=turn_id, trace=trace
        )

        # One entry per exercise; if the agent retried a save within the turn,
        # prefer the non-duplicate result.
        saved_by_exercise: dict[str, dict] = {}
        for e in trace:
            if (
                e.get("tool") == "log_session"
                and isinstance(e.get("result"), dict)
                and e["result"].get("saved")
            ):
                r = e["result"]
                key = r.get("exercise_id")
                if key not in saved_by_exercise or (saved_by_exercise[key].get("duplicate") and not r.get("duplicate")):
                    saved_by_exercise[key] = r
        saved_sessions = list(saved_by_exercise.values())
        mood = turn_mood(trace, saved_sessions)
        tone = choose_tone(saved_sessions, mood)

        audio_base64 = None
        audio_mime = voice.MP3_MIME
        try:
            spoken, audio_mime = await asyncio.to_thread(voice.speak, reply_text, tone)
            audio_base64 = base64.b64encode(spoken).decode("ascii")
        except Exception:
            audio_base64 = None  # speech failure must not fail the request

        return {
            "turn_id": turn_id,
            "session_id": new_session_id,
            "transcript": text,
            "reply_text": reply_text,
            "tone": tone,
            "audio_base64": audio_base64,
            "audio_mime": audio_mime,
            "mood": mood,
            "saved_sessions": saved_sessions,
            "trace": trace,
        }
    finally:
        tools.TRACE.reset(trace_token)
        tools.TURN_ID.reset(turn_token)


@app.get("/api/sessions")
async def get_sessions(exercise: str | None = None, limit: int = 5) -> list[dict]:
    """Sessions newest first (one exercise if given), each with total_reps and is_seed."""
    ex_id = db.resolve_exercise(exercise) if exercise else None
    if exercise and ex_id is None:
        return []
    rows = await asyncio.to_thread(db.list_sessions, ex_id, limit)
    return [{**r, "total_reps": tools.total_reps(r["reps"])} for r in rows]


@app.get("/api/exercises")
async def get_exercises() -> list[dict]:
    return await asyncio.to_thread(db.list_exercises)


class MoodIn(BaseModel):
    mood: str


@app.post("/api/mood")
async def post_mood(body: MoodIn) -> dict:
    """Set the mood on all non-seed sessions saved today (UTC)."""
    if body.mood not in MOODS:
        raise HTTPException(status_code=400, detail="bad_mood: mood must be one of low, active, pumped")
    updated = await asyncio.to_thread(db.set_mood_today, body.mood)
    return {"mood": body.mood, "updated": updated}


@app.post("/api/reset")
async def post_reset() -> dict:
    """Delete non-seed sessions, re-create the seed with fresh dates, drop agent sessions."""
    await asyncio.to_thread(db.reset_db)
    dropped = agent_module.drop_sessions()
    return {"reset": True, "dropped_agent_sessions": dropped}


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


# Registered last so the /api/* routes above match first.
app.mount("/", StaticFiles(directory=STATIC_DIR), name="static")
