# VoiceFit

Voice-first workout logging that remembers what "last time" means, and how you felt.

Speak to the page (or type as a fallback); the audio is transcribed, a Mistral Agent
decides what to log using your history, and the reply is spoken back. The page shows
the transcript, the coach reply, the saved sessions with beat/held/dropped badges,
and the tool-call trace.

Built at the Mistral Le Chonk London hackathon, 21 November 2026, with Mistral Vibe,
Mistral Large 4, Mistral Agents and Voxtral 3.

## Architecture

```
browser (static/index.html + app.js + style.css, no frameworks)
  |  POST /api/turn  (multipart: audio blob  XOR  transcript, + session_id)
  v
app/main.py  FastAPI
  |  audio path:  app/voice.py::transcribe  -> Voxtral 3 transcription
  |  text path:   transcript used as-is (test path / on-stage fallback)
  v
app/agent.py  Mistral Agent (mistralai-agents) on mistral-large-4
  |  three tools, thin async wrappers over the pure functions in app/tools.py:
  |    get_last_session(exercise)   log_session(exercise, weight, unit, reps, mood)
  |    get_mood_history(mood)
  |  multi-turn: start_session() / agent.session(id) rebind, session.run(msg)
  v
app/tools.py  ALL arithmetic and comparisons live here (totals, beat/held/dropped,
  |  mood counts, lb->kg conversion, duplicate-turn guard) - never in the model.
  |  Every tool call appends {tool, args, result, ms} to the turn's trace.
  v
app/db.py  SQLite voicefit.db: exercises (8, with aliases), sessions, 19-row seed
  |  reset, mood-of-today, per-exercise history queries
  v
tone chosen in code (pleased if any save beat, else calm if mood low, else neutral)
  -> app/voice.py::speak -> Voxtral 3 TTS (mp3, one preset voice, inline tone tags)
  -> response JSON: turn_id, session_id, transcript, reply_text, tone,
     audio_base64, audio_mime, mood, saved_sessions, trace

Other routes: GET /api/sessions?exercise=&limit=5 (newest first, total_reps, is_seed),
GET /api/exercises, POST /api/mood {"mood": ...} (sets mood on today's non-seed
sessions), POST /api/reset (reseed + drop agent sessions), GET / -> static/index.html.
```

## How to run

```bash
uv sync
cp .env.example .env        # put your MISTRAL_API_KEY=... in .env (never committed)
uv run uvicorn app.main:app --port 8000
# open http://localhost:8000/  -- hold the mic button and speak, or type in the box
```

Checks (all stdlib + installed deps only):

```bash
uv run pytest -q                                            # unit + contract tests
uv run python scripts/smoke.py                              # Task 0: live API proof
uv run python scripts/voice_check.py                        # Task 3: transcribe + 3 tones
uv run python scripts/replay.py --base-url http://127.0.0.1:8000   # server must be up
```

## Where each Mistral service is used

- **Voxtral 3 transcription** — `app/voice.py::transcribe()`: model
  `voxtral-mini-transcribe-3-0`, file upload with `context_bias` built from
  `app/vocab.py::context_bias_terms()` (exercise names/aliases + unit words).
- **Voxtral 3 speech** — `app/voice.py::speak()`: model `voxtral-mini-tts-3-0`,
  one preset voice (`voice_478`), mp3 output; tone (`pleased`/`calm`/`neutral`)
  maps to inline `[emotion=…]`/`[pace=…]` tags in the input text.
- **Mistral Agent** — `app/agent.py`: `agents.Agent(model="mistral-large-4")` from
  `mistralai-agents`, instructions in `docs/BUILD-BRIEF.md` §Agent, three SDK
  tools wrapping `app/tools.py`. The model never does arithmetic and never guesses
  a weight/unit; totals, comparisons and mood counts come from the tools.
- **Mistral Vibe** — the coding agent that built this repository: coordinator,
  coder, reviewer and tester roles in separate git worktrees (`docs/WORKFLOW.md`,
  `docs/agents/`), all code on `main` through pull requests.
- Exact verified model IDs, SDK parameter names, package versions and gotchas are
  in `NOTES.md` (proven live by `scripts/smoke.py` in Task 0).

## Test results (all run 2026-11-21, this checkout, server on port 8000)

| Check | Command | Result |
|---|---|---|
| Unit + contract tests | `uv run pytest -q` | **99 passed** (17:06 UTC) |
| Live API smoke (Task 0) | `uv run python scripts/smoke.py` | exit 0, all PASS (transcript contains "RDL", agent session continued, 3 tone mp3s) |
| Voice check (Task 3) | `uv run python scripts/voice_check.py` | exit 0, transcript contains "RDL", 3 valid mp3s |
| End-to-end replay (Task 6) | `uv run python scripts/replay.py --base-url http://127.0.0.1:8000` | **REPLAY: 8/8 passed**, exit 0 (16:50–16:51 UTC; also 8/8 on main at 16:33) |
| Replay variations (Task 6) | 5 extra paraphrases of each of the 8 kinds, same per-case checks | **36/40 passed (90%)** (16:52–17:04 UTC) |

Variation pass rate per kind: kind 1 (RDL same weight + correction) 3/5, kind 2
(mood question) 5/5, kind 3 (same-conversation save) 5/5, kind 4 (two exercises)
5/5, kind 5 (no history -> asks weight) 5/5, kind 6 (same-conversation weight
answer) 4/5, kind 7 (lb conversion) 5/5, kind 8 (unknown exercise) 4/5.

The 4 failures, honestly: two kind-1 paraphrases phrased the correction as
"five, five, five, but the last one was six" were logged as four sets [5,5,5,6]
instead of the corrected [5,5,6]; the tersest kind-6 variation ("Forty.") saved
nothing; one kind-8 variation ("Arms: curls...") asked for the weight without
calling a tool first. The 8 canonical replay transcripts all pass deterministically.

## Where things are

- `AGENTS.md` — rules every coding agent reads first
- `docs/PLAN.md` — product, prize alignment, schedule, demo script
- `docs/BUILD-BRIEF.md` — technical specification and tasks
- `docs/UI-SPEC.md` — the page
- `docs/WORKFLOW.md` — worktrees and pull requests
- `docs/TASKS.md` — live task board
- `docs/agents/` — coordinator, coder, reviewer and tester roles
- `NOTES.md` — verified Mistral model IDs / SDK names (Task 0)
- `app/` — `db.py` storage+seed, `vocab.py` exercises, `tools.py` logic+trace,
  `voice.py` Voxtral, `agent.py` Mistral Agent, `main.py` FastAPI routes
- `static/` — the page (one HTML, one JS, one CSS, mock-turn.json)
- `scripts/` — `smoke.py`, `voice_check.py`, `replay.py`
- `tests/` — pytest suite (db, tools, turn assembly)
