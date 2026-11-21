# NOTES.md — Verified Mistral names (Task 0)

Verified against the **live API** on 2026-11-21 by `scripts/smoke.py` (run: `uv run python scripts/smoke.py`, exit 0, all checks PASS). Environment: Windows, Python 3.12.16 (uv-managed), `mistralai==3.8.0`, `mistralai-agents==1.1.3`. Later tasks must use these names, not the brief.

## Packages and versions

| Package | Version | Notes |
|---|---|---|
| `mistralai` | 3.8.0 | client + audio + agents SDKs live in one namespace |
| `mistralai-agents` | 1.1.3 | installs into `mistralai.agents` / `mistralai.vibe_agents` |
| Python | 3.12.x | `requires-python = ">=3.12,<3.13"` in `pyproject.toml` |

Pinning to 3.12 matters: on Python 3.14/3.15 `mistralai` 3.8.0 pulls `zstandard`, which has no wheel for those versions and fails to build on Windows without MSVC. On 3.12 the wheel installs fine.

## Model IDs (verified in `client.models.list()`)

| Use | Model ID | Also available |
|---|---|---|
| Agent | `mistral-large-4` | `mistral-large-4-0`, `mistral-large-latest`, `mistral-large-2512` |
| Transcription | `voxtral-mini-transcribe-3-0` | `voxtral-mini-transcribe-3`, `voxtral-small-transcribe-3-0`, `voxtral-mini-latest` |
| TTS | `voxtral-mini-tts-3-0` | `voxtral-mini-tts-3`, `voxtral-mini-tts-2603`, `voxtral-mini-tts-latest` |

The brief's ⚠ guesses `voxtral-mini-transcribe-3-0`, `voxtral-mini-tts-3-0` and `mistral-large-4` are all correct.

## Client

```python
from mistralai.client import Mistral
client = Mistral(api_key=os.environ["MISTRAL_API_KEY"])
```

Audio lives under `client.audio` (`speech`, `transcriptions`, `voices`, ...).

## Transcription (`app/voice.py` will use this)

```python
res = client.audio.transcriptions.complete(
    model="voxtral-mini-transcribe-3-0",
    file={"file_name": "clip.wav", "content": audio_bytes},  # FileTypedDict: file_name + content (bytes or IO)
    language="en",                # optional, boosts accuracy
    context_bias=["rdl", "rdls", "romanian deadlift", ...],   # the context-bias parameter
)
text = res.text                   # TranscriptionResponse.text
```

- **context-bias parameter name and shape:** `context_bias`, a plain **list of strings** (`Iterable[str]`), sent as a multipart field on `POST /v1/audio/transcriptions`. Verified working: a synthesized clip saying "RDLs, eighty kilos, five, five, six" transcribed as `rdls, 80 kilos, 5, 5.` / `RDLs, 80 kilos, 556.` across runs — always containing "RDL" with the bias list.
- **Formats:** wav and mp3 uploads are both accepted by the endpoint (both transcribed correctly in the smoke run). The browser's webm/opus upload could not be generated locally (no microphone, no ffmpeg on this machine), so webm/opus itself is **not tested** — mp3 standing in for "non-wav" was accepted. Task 3 should still send the browser blob as-is and convert to wav only if the API rejects it.
- Caveat: on synthetic (TTS-generated) speech, spoken digits can come out merged ("556", "5'5\"") — real microphone audio should be better; the done-when check only requires "RDL".

## Speech (`app/voice.py` will use this)

```python
import base64
resp = client.audio.speech.complete(
    model="voxtral-mini-tts-3-0",
    input="[emotion=happy]Logged. Sixteen reps at eighty kilos.",
    voice_id="voice_478",          # preset voice slug works as voice_id
    response_format="mp3",         # Literal["pcm","wav","mp3","flac","opus"]
)
audio_bytes = base64.b64decode(resp.audio_data)   # SpeechResponse.audio_data, base64
```

- **Voice:** one preset voice, slug `voice_478` (en_us, kind `pvc`; UUID `01a0f6db-3095-7682-b70f-6a15ebfba70a` also accepted). List presets with `client.audio.voices.list(limit=100, type_="preset")` (66 presets; endpoint deprecated in favour of `GET /v2/audio/voices` but works).
- **Tone is set inline in `input`, not via separate voices or SDK parameters.** Voxtral 3 keeps one voice and reads square-bracket tags: `[emotion=<value>]`, `[pace=<value>]`, combinable as `[emotion=calm][pace=slow]`. The tag is not spoken aloud.
  - 34 emotions, including `happy`, `calm`, `excited`, `proud`, `warm`, `confident`, `sad`, `somber`.
  - 5 paces: `very-slow`, `slow`, `moderate`, `fast`, `very-fast`.
  - **Unsupported tag values are NOT rejected** — `[emotion=ecstatic]` returns normal audio and the tag is silently ignored. Only use values from the tables.
  - VoiceFit tone mapping (verified, three mp3s written by `scripts/smoke.py`):
    - `pleased` → `[emotion=happy]`
    - `calm` → `[emotion=calm][pace=slow]`
    - `neutral` → no tag (Voxtral TTS 3 infers emotion from the text itself)
- `expressiveness` (float ≥ 1.0) also exists on the call if a stronger delivery is ever needed.

## Agent (`app/agent.py` will use this)

```python
from mistralai import agents

@agents.tool                      # bare decorator: name from function, description from docstring
def get_last_session(exercise: str) -> dict:
    """Look up the most recent saved session for an exercise."""
    ...

agent = agents.Agent(
    model="mistral-large-4",
    instructions="...",
    tools=[get_last_session, ...],   # module-scope typed functions
)
```

- **Tools must be decorated at module scope.** `@agents.tool` inside a function raises `ValueError: Decorated tools must be defined at module scope`. Every parameter must be typed (the SDK builds the input schema from the signature; the docstring becomes the description).
- **Running and continuing a session** (all verified live):

```python
session = await agent.start_session()
first  = await session.run("Call the ping tool with note 'first'")   # TurnState
second = await session.run("Now ... note 'second'")                   # same session_id
handle = agent.session(first.session_id)   # rebind by id, same event loop
third  = await handle.run("... note 'third'")
```

  - `await agent.run(msg)` starts a session, runs **one** turn, and **closes the session** when it returns — its `session_id` cannot be continued afterwards (`SessionTerminatedError: The local Session has ended`). Do not use `agent.run()` for multi-turn; use `start_session()` and keep the handle (or rebind with `agent.session(session_id)` inside the same process/event loop, which is what `/api/turn` will do across requests in the uvicorn process).
  - The returned `Completed` record has `.session_id`, `.turn_id`, `.text` (the reply), and `.tool_calls` — a tuple of `ToolCall(name, arguments)` where `name` is the full tool ID, e.g. `client.ping`. Use `tool_calls` to confirm/inspect calls.
  - Tool functions may be sync; wrap blocking work (sqlite) with `asyncio.to_thread` inside them.
  - Default `permission_mode="auto"` runs tool calls without asking — right for a headless server.
- **API key for the agent SDK:** it reads the key from the environment (`MISTRAL_CLIENT_API_KEY`, falling back to `MISTRAL_API_KEY`) — not from a client constructor arg. Set `os.environ["MISTRAL_API_KEY"]` before running (the smoke script does this from `.env`).

## What did not work / gotchas

1. `mistralai` 3.8.0 on Python 3.14/3.15 → `zstandard` sdist build fails on Windows (needs MSVC). Fixed by pinning `requires-python = ">=3.12,<3.13"`.
2. `@agents.tool` on a function defined inside another function → `ValueError`. Tools live at module scope.
3. `agent.run(...)` then `agent.session(id).run(...)` → `SessionTerminatedError`. Use `start_session()` for multi-turn sessions.
4. `Mistral(api_key=...)` covers `client.audio.*`; the **agents** SDK only reads the key from env vars.
5. Browser webm/opus transcription not tested locally (no mic/ffmpeg); wav and mp3 both accepted.
6. Audio "plays" was verified by file magic (`ID3` header) and size, not by an actual speaker — no audio output device in this environment.

## Smoke check output (2026-11-21, exit 0)

```
[PASS] tts tone 'pleased' -- smoke-pleased.mp3 30312 bytes, mp3 magic=True
[PASS] tts tone 'calm' -- smoke-calm.mp3 35096 bytes, mp3 magic=True
[PASS] tts tone 'neutral' -- smoke-neutral.mp3 35020 bytes, mp3 magic=True
[PASS] transcript contains 'RDL' -- 'rdls, 80 kilos, 5, 5.'
[PASS] mp3 upload accepted by transcriber -- 'RDLs, 80 kilos, 556.'
[PASS] agent turn 1 completed -- session_id=df108430-...
[PASS] dummy tool called in turn 1 -- ['client.ping']
[PASS] same session continued -- df108430-... == df108430-...
[PASS] dummy tool called in turn 2 -- ['client.ping']
[PASS] session rebound by id ran turn 3 -- tool calls=['client.ping']
SMOKE PASS: all checks passed
```
