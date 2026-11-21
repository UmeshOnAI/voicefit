# VoiceFit — Build Brief for Mistral Vibe

This is the technical specification for VoiceFit. Work through it one task at a time. Each task lists the files it owns and the checks that prove it is done. Do not add features that are not in this brief.

## How to use this brief

Every agent first reads `AGENTS.md` and its own role file in `docs/agents/`. The coordinator assigns one task at a time from `docs/TASKS.md`. A coder does that task only, touches only the files the task owns, runs its checks, and opens a pull request as described in `docs/WORKFLOW.md`.

Tasks are in two lanes that own different files, so they can run in parallel: **core** (everything under `app/`, `scripts/`, `tests/`) and **ui** (everything under `static/`).

## Product in one paragraph

A lifter speaks to a web page. The audio is transcribed by Voxtral 3. A Mistral Agent on `mistral-large-4` reads the transcript and uses three tools to look up previous sessions, save new ones, and look up how past sessions went in a given mood. The reply is spoken back by Voxtral 3 text-to-speech. The page shows the transcript, previous and new sessions, and a trace of the tool calls.

## Hard rules

1. **Names in this brief that come from Mistral's docs are unverified.** Model IDs, SDK method names and parameter names are marked ⚠. Task 0 verifies them against the live API and current docs and writes the working values to `NOTES.md`. Later tasks use `NOTES.md`, not this brief, for those names.
2. **The model never does arithmetic.** Totals, comparisons and mood counts are computed in `tools.py`. The agent's reply states only numbers a tool returned.
3. **Never guess a weight or a unit.** If neither the user nor history supplies it, the agent asks one question and saves nothing.
4. **The API key lives in `.env`** as `MISTRAL_API_KEY`. `.env` is in `.gitignore`. Never print or commit it.
5. **No frameworks on the front end.** One HTML file, one JS file, one CSS file.
6. **If something in this brief cannot work as written, stop and say so** instead of inventing a workaround.

## Stack

- Python 3.12, `uv`, FastAPI, uvicorn, `sqlite3` from the standard library, pytest
- `mistralai` (transcription and speech) and `mistralai-agents` ⚠ (agent)
- Static front end served by FastAPI

## Layout

```
.env.example            MISTRAL_API_KEY=
.gitignore
pyproject.toml
NOTES.md                Task 0 findings (verified names)
README.md
AGENTS.md               rules every agent reads first
docs/                   PLAN, BUILD-BRIEF, UI-SPEC, WORKFLOW, TASKS, agents/
app/
  main.py               FastAPI app and routes            (Task 5)
  db.py                 schema, seed, reset, queries      (Task 1)
  tools.py              pure tool logic + trace           (Task 2)
  voice.py              transcribe(), speak()             (Task 3)
  agent.py              agent definition and run_turn()   (Task 5)
  vocab.py              exercises and aliases             (Task 1)
static/
  index.html  app.js  style.css  mock-turn.json           (Task 4)
scripts/
  smoke.py              Task 0
  replay.py             typed-transcript replay tests     (Task 6)
tests/
  test_db.py  test_tools.py
```

## Data model

SQLite file `voicefit.db`.

```sql
CREATE TABLE exercises (
  id    TEXT PRIMARY KEY,          -- e.g. romanian_deadlift
  name  TEXT NOT NULL,             -- Romanian deadlift
  aliases TEXT NOT NULL            -- JSON list of lowercase strings
);

CREATE TABLE sessions (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  exercise_id   TEXT NOT NULL REFERENCES exercises(id),
  performed_at  TEXT NOT NULL,     -- ISO 8601, UTC
  weight_kg     REAL NOT NULL,
  reps          TEXT NOT NULL,     -- JSON list of ints, one per set, e.g. [5,5,6]
  mood          TEXT,              -- 'low' | 'active' | 'pumped' | NULL
  raw_transcript TEXT,
  turn_id       TEXT,              -- id of the /api/turn request that saved it
  is_seed       INTEGER NOT NULL DEFAULT 0,
  UNIQUE (turn_id, exercise_id)    -- a retried tool call cannot save twice
);
```

### Exercises (`vocab.py`)

| id | name | aliases |
|---|---|---|
| romanian_deadlift | Romanian deadlift | rdl, rdls, romanian deadlift, romanian deadlifts |
| bench_press | Bench press | bench, bench press |
| back_squat | Back squat | squat, squats, back squat |
| overhead_press | Overhead press | ohp, overhead press, shoulder press |
| deadlift | Deadlift | deadlift, deadlifts |
| barbell_row | Barbell row | row, rows, barbell row, bent over row |
| pull_up | Pull-up | pull up, pull ups, pullups, chin ups |
| lunge | Lunge | lunge, lunges |

`vocab.py` also exposes `context_bias_terms()`: every name and alias plus `reps`, `sets`, `kilos`, `kg`, `pounds`.

### Seed rows

`performed_at` = now minus the given number of days. All rows `is_seed = 1`. Overhead press and the last four exercises have no sessions.

| Exercise | Days ago | kg | Reps | Mood |
|---|---|---|---|---|
| romanian_deadlift | 28 | 75 | 5,5,5 | active |
| romanian_deadlift | 24 | 75 | 5,5,5 | low |
| romanian_deadlift | 21 | 77.5 | 5,5,5 | pumped |
| romanian_deadlift | 17 | 77.5 | 5,5,5 | low |
| romanian_deadlift | 14 | 80 | 5,5,4 | active |
| romanian_deadlift | 10 | 80 | 5,5,5 | low |
| romanian_deadlift | 7 | 80 | 5,4,4 | low |
| romanian_deadlift | 3 | 80 | 5,5,5 | active |
| bench_press | 27 | 60 | 8,8,8 | active |
| bench_press | 23 | 60 | 8,7,6 | low |
| bench_press | 20 | 60 | 8,8,8 | pumped |
| bench_press | 16 | 62.5 | 8,8,7 | active |
| bench_press | 13 | 62.5 | 7,6,6 | low |
| bench_press | 9 | 62.5 | 8,8,8 | pumped |
| bench_press | 6 | 62.5 | 8,7,6 | low |
| bench_press | 2 | 62.5 | 8,8,8 | active |
| back_squat | 26 | 100 | 5,5,5 | active |
| back_squat | 12 | 100 | 5,5,5 | pumped |
| back_squat | 5 | 102.5 | 5,5,5 | active |

Expected from this seed: low-mood Romanian deadlift = 4 sessions, 3 held or beat; low-mood bench press = 3 sessions, 0 held or beat.

## Comparison rule (`tools.compare(previous, new)`)

Compare a session with the immediately preceding session of the same exercise.

| Condition | outcome |
|---|---|
| no previous session | `first` |
| new weight > previous weight | `beat` |
| same weight, total reps higher | `beat` |
| same weight, total reps equal | `held` |
| anything else | `dropped` |

Weights are "the same" when they differ by less than 0.05 kg. `delta_reps` = new total reps minus previous total reps, and is `null` unless the weights are the same.

## Tool contracts (`tools.py`)

Plain functions that take and return JSON-serialisable values. No Mistral imports in this file. Every call appends `{tool, args, result, ms}` to the current request's trace (a `contextvars.ContextVar` holding a list). The current `turn_id` is also read from a context variable.

### `get_last_session(exercise: str) -> dict`

Resolves `exercise` through names and aliases, case-insensitive.

```json
{"found": true, "exercise_id": "romanian_deadlift", "exercise_name": "Romanian deadlift",
 "performed_at": "2026-11-18T10:00:00Z", "weight_kg": 80.0, "reps": [5,5,5],
 "total_reps": 15, "mood": "active"}
```

`{"found": false, "exercise_id": "overhead_press", "exercise_name": "Overhead press"}` when there is no history.
`{"found": false, "error": "unknown_exercise", "known": [...names]}` when the exercise does not resolve.

### `log_session(exercise: str, weight: float, unit: str, reps: list[int], mood: str | None = None) -> dict`

Validation, in order. On failure return `{"saved": false, "error": "<code>", "message": "<one sentence>"}` and write nothing.

- `unknown_exercise`: does not resolve
- `bad_unit`: `unit` not `kg` or `lb`
- `bad_weight`: not in 0 < kg ≤ 500 after conversion
- `bad_reps`: not 1 to 10 sets, or any value outside 1 to 50
- `bad_mood`: not null and not one of the three values

Behaviour:

- Converts `lb` to kg with 0.45359237, rounded to 2 decimal places.
- If `mood` is null, uses the mood of the most recent non-seed session saved today, if any.
- If a row already exists for this `(turn_id, exercise_id)`, returns that row's result with `"duplicate": true` and writes nothing.

```json
{"saved": true, "session_id": 20, "exercise_id": "romanian_deadlift",
 "exercise_name": "Romanian deadlift", "weight_kg": 80.0, "reps": [5,5,6],
 "total_reps": 16, "mood": "low",
 "previous": {"performed_at": "...", "weight_kg": 80.0, "reps": [5,5,5], "total_reps": 15},
 "outcome": "beat", "delta_reps": 1}
```

### `get_mood_history(mood: str) -> dict`

For every session with that mood that has a previous session of the same exercise, compute `outcome`.

```json
{"mood": "low", "total_sessions": 7,
 "by_exercise": [
   {"exercise_id": "romanian_deadlift", "exercise_name": "Romanian deadlift",
    "sessions": 4, "held_or_beat": 3, "dropped": 1},
   {"exercise_id": "bench_press", "exercise_name": "Bench press",
    "sessions": 3, "held_or_beat": 0, "dropped": 3}],
 "suggested_exercise_id": "romanian_deadlift"}
```

`by_exercise` is sorted by `held_or_beat / sessions`, highest first. `suggested_exercise_id` is the first entry with at least 2 sessions, or `null`. An invalid mood returns `{"error": "bad_mood"}`.

## HTTP API (`main.py`)

### `POST /api/turn` (multipart form)

Fields: `audio` (file, optional), `transcript` (text, optional), `session_id` (text, optional). Exactly one of `audio` or `transcript` is required. With `transcript`, transcription is skipped; this is the test path and the on-stage fallback.

```json
{
  "turn_id": "uuid",
  "session_id": "agent session id to send back on the next turn",
  "transcript": "RDLs, same weight as last time...",
  "reply_text": "Logged. Sixteen reps at 80 kilos. That's one more than last time.",
  "tone": "pleased",
  "audio_base64": "...", "audio_mime": "audio/mpeg",
  "mood": "low",
  "saved_sessions": [ { ...log_session result... } ],
  "trace": [ {"tool": "get_last_session", "args": {...}, "result": {...}, "ms": 4} ]
}
```

`tone` is chosen in code: `pleased` if any saved session has outcome `beat`; else `calm` if the current mood is `low`; else `neutral`. `mood` is the mood on the sessions saved this turn, else the `mood` passed to `get_mood_history` this turn, else null. If speech generation fails, return the turn with `audio_base64: null` and do not fail the request.

### Other routes

- `GET /api/sessions?exercise=<id>&limit=5` → newest first, each with `total_reps` and `is_seed`
- `GET /api/exercises` → id and name list
- `POST /api/mood` with `{"mood": "low"}` → sets that mood on all non-seed sessions saved today
- `POST /api/reset` → deletes non-seed sessions, re-creates the seed with fresh dates, drops agent sessions
- `GET /` → `static/index.html`

## Agent (`agent.py`)

Uses the `mistralai-agents` SDK ⚠ with model `mistral-large-4` ⚠. Three thin async wrappers decorated as SDK tools call the functions in `tools.py`. The SDK requires tool functions at module scope with every parameter typed; do not block inside them (wrap database calls with `asyncio.to_thread`).

`run_turn(transcript, session_id) -> (reply_text, session_id)` starts a new agent session when `session_id` is missing and continues the existing one otherwise.

### Instructions

```
You are VoiceFit. A lifter speaks to you in the gym and you receive the transcript.
They may log one exercise between sets, log several exercises in one go at the end,
tell you how they feel, or ask what to do.

Logging:
- Work out each exercise, its weight and unit, and the reps for every set as a list.
- If they refer to a previous session ("same as last time", "same weight"), call
  get_last_session for that exercise first and use its weight in kg.
- Apply spoken corrections: "five, five, and five... actually six on the last set"
  means [5, 5, 6].
- Never guess a weight or a unit. If either is missing and history does not supply
  it, ask one short question and do not call log_session for that exercise.
- Call log_session once per exercise.

Mood:
- If they say how they feel, map it to exactly one of: low, active, pumped.
  Pass it as mood on log_session calls in this conversation.
- If they ask what to do given how they feel, call get_mood_history with that mood.
  Recommend the suggested exercise and state the counts it returned, for example
  "held or beat your numbers 3 of 4 times". If there is no suggestion, say there is
  not enough history yet.

Replying:
- One or two short sentences, written to be spoken aloud. No lists, no symbols.
- State only numbers that a tool returned. Do not calculate anything yourself.
- After logging, say the total reps and weight, and the comparison with last time
  if there is one.
- Reply in the language the lifter used.
- Do not give medical or injury advice.
```

## Voice (`voice.py`)

- `transcribe(audio_bytes, filename) -> str` — file transcription with model `voxtral-mini-transcribe-3-0` ⚠ and the `context_bias` ⚠ parameter set from `vocab.context_bias_terms()`. If the browser's webm/opus upload is rejected, convert to wav before sending and note it in `NOTES.md`.
- `speak(text, tone) -> (bytes, mime)` — model `voxtral-mini-tts-3-0` ⚠, one preset voice ⚠, mp3 output. `tone` (`pleased`, `calm`, `neutral`) maps to the emotion and pace controls ⚠ found in Task 0. If no such controls exist, use the same voice for all three and record that in `NOTES.md`.

## Page (`static/`)

The full specification is `docs/UI-SPEC.md` (wireframe, element ids, states, error handling, mock response). Summary, top to bottom:

1. **Mic button** (hold or click to start and stop; `MediaRecorder`) and a **text box with Send** that posts `transcript` instead of audio.
2. **Mood chips:** Low, Active, Pumped. Highlights the `mood` from the last turn; clicking one calls `POST /api/mood`.
3. **Heard:** the transcript.
4. **Coach:** `reply_text`; plays the audio automatically.
5. **Sessions:** for each exercise in `saved_sessions`, its last four sessions from `GET /api/sessions`, with the new one highlighted, an outcome badge (beat, held, dropped, first), and seeded rows marked "seed". Before any turn, show Romanian deadlift history.
6. **Tool trace:** collapsible; one line per call with tool name, arguments and result.
7. **Reset demo** button.

Large type, readable from the back of a room on a projector. No charts. Show a visible "Listening" and "Thinking" state.

## Tasks

### Task 0 — Prove the API (lane: core) · `scripts/smoke.py`, `NOTES.md`, `pyproject.toml`, `.env.example`, `.gitignore`

Check the current Mistral docs for each ⚠ item, then prove it with a script that:

1. Transcribes a short recorded clip saying "RDLs, eighty kilos, five, five, six", with context bias.
2. Runs an agent on `mistral-large-4` with one dummy tool, confirms the tool is called, and continues the same session with a second message.
3. Generates speech for one sentence in each of the three tones and saves three mp3 files.

Write to `NOTES.md`: the exact working model IDs, package versions, the context-bias parameter name and shape, the voice ID, how tone is set, how a session is continued, and anything that did not work.

**Done when:** the script prints a transcript containing "RDL", prints both agent replies, and three audio files play.

### Task 1 — Database and seed (lane: core) · `app/db.py`, `app/vocab.py`, `tests/test_db.py`

Schema, exercise table, alias resolution, seed, reset, and the queries the tools need.

**Done when:** tests pass for alias resolution ("RDLs" → `romanian_deadlift`), seed row count (19), the last Romanian deadlift being 80 kg [5,5,5], and reset restoring the seed after extra rows are added.

### Task 2 — Tools (lane: core) · `app/tools.py`, `tests/test_tools.py`

The comparison rule, three tools, validation, trace.

**Done when** tests pass for:

- `log_session("rdls", 80, "kg", [5,5,6])` → `beat`, `delta_reps` 1, `total_reps` 16
- the same call twice with one `turn_id` → one row, second result `duplicate`
- `[5,5,5]` → `held`; `[5,5,4]` → `dropped`; 82.5 kg → `beat` with `delta_reps` null
- 135 lb → 61.23 kg
- each validation error code
- `get_last_session("overhead press")` → `found` false
- `get_mood_history("low")` on the seed → deadlift 4 sessions and 3 held or beat, bench 3 and 0, suggestion `romanian_deadlift`
- the trace list holds one entry per call

### Task 3 — Voice (lane: core) · `app/voice.py`

Uses the names in `NOTES.md`.

**Done when:** a script transcribes a recorded clip and produces playable audio in each tone.

### Task 4 — Page (lane: ui) · `static/*`

Build against `static/mock-turn.json`, a hand-written example of the `/api/turn` response in this brief, so it needs no backend.

**Done when:** loading the page with the mock shows the transcript, reply, highlighted new row with a "beat" badge, the mood chip set to Low, and an expandable trace; the mic records and produces a blob; the text box posts a transcript.

### Task 5 — Agent and endpoint (lane: core) · `app/agent.py`, `app/main.py`

Wire transcription, agent, tools, tone choice and speech into `/api/turn`; add the other routes.

**Done when:** posting the transcript "RDLs, same weight as last time. Five, five, and five, actually six on the last set." returns one saved session with reps [5,5,6] at 80 kg, a trace with `get_last_session` then `log_session`, tone `pleased`, and audio. Then the same result from a spoken clip in the browser.

### Task 6 — Replay tests and hardening (lane: core; tester writes the script) · `scripts/replay.py`

A script that resets, posts each typed transcript below to `/api/turn`, and checks the outcome. Generate five more variations of each kind and report how many pass.

| Transcript | Expect |
|---|---|
| RDLs, same weight as last time. Five, five, and five, actually six on the last set. | 1 save: 80 kg, [5,5,6], beat |
| I'm feeling low today, what should I do? | 0 saves; `get_mood_history("low")` in trace; reply names Romanian deadlift; tone `calm`; mood `low` |
| (same conversation) RDLs, same as last time, five, five, five. | 1 save with mood `low`, outcome held, tone `calm` |
| Bench, 62.5 kilos, eight, seven, seven, and squats same as last time, five, five, five. | 2 saves: bench dropped, squat 102.5 kg held |
| Overhead press, same as last time, five and five. | 0 saves; reply asks for the weight |
| (same conversation) Forty kilos. | 1 save: overhead press 40 kg [5,5], outcome first |
| Bench, one thirty-five pounds, five, five. | 1 save: 61.23 kg |
| Did some curls, ten, ten, ten. | 0 saves; reply says the exercise is not known |

**Done when:** all eight pass, and the pass rate for the generated variations is written to `README.md`.

## Out of scope

Charts, dashboards, authentication, multiple users, calendar, realtime streaming transcription, Mistral Workflows, estimated one-rep max, programme generation, injury or medical advice, any fourth tool.
