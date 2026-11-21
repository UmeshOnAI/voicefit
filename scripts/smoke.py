#!/usr/bin/env python3
"""Task 0 smoke check: prove the Mistral API pieces VoiceFit needs.

Run from the repo root:

    uv run python scripts/smoke.py

Against the live API this script proves:

1. Speech generation: model ``voxtral-mini-tts-3-0`` speaks one sentence in each
   of the three tones (pleased, calm, neutral) and writes ``smoke-<tone>.mp3``.
2. Transcription: a clip saying "RDLs, eighty kilos, five, five, six" (synthesized
   with the TTS model, as there is no microphone here) is transcribed by
   ``voxtral-mini-transcribe-3-0`` with a ``context_bias`` list, and the printed
   transcript contains "RDL".
3. Agent: an agent on ``mistral-large-4`` with one dummy tool calls that tool, and
   the same session continues with a second message.

Each check prints PASS or FAIL; the exit code is 1 if any check fails.
The API key is read from ``.env`` and never printed.
"""

import asyncio
import base64
import os
import sys
from importlib.metadata import version
from pathlib import Path

from mistralai import agents

ROOT = Path(__file__).resolve().parent.parent

# Verified in Task 0 against the live API; see NOTES.md.
TRANSCRIBE_MODEL = "voxtral-mini-transcribe-3-0"
TTS_MODEL = "voxtral-mini-tts-3-0"
AGENT_MODEL = "mistral-large-4"
VOICE_ID = "voice_478"  # preset en_us voice, kind pvc (Voxtral 3: one voice, inline emotion tags)

# Same shape as app/vocab.py context_bias_terms() (Task 1); kept inline because
# Task 0 runs before vocab.py exists.
CONTEXT_BIAS = [
    "romanian deadlift", "romanian deadlifts", "rdl", "rdls",
    "bench press", "bench", "back squat", "squat", "squats",
    "overhead press", "ohp", "shoulder press", "deadlift", "deadlifts",
    "barbell row", "row", "rows", "bent over row",
    "pull up", "pull ups", "pullups", "chin ups", "lunge", "lunges",
    "reps", "sets", "kilos", "kg", "pounds",
]

# Tone -> inline tags in `input` (docs: Emotion and pace tags). Neutral uses no
# tag: Voxtral TTS 3 infers emotion from the text itself.
TONE_TAGS = {
    "pleased": "[emotion=happy]",
    "calm": "[emotion=calm][pace=slow]",
    "neutral": "",
}

CLIP_SENTENCE = "RDLs, eighty kilos, five, five, six."
REPLY_SENTENCE = "Logged. Sixteen reps at eighty kilos. That is one more than last time."

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail else ""))
    if not ok:
        failures.append(name)


def load_api_key() -> str:
    key = os.environ.get("MISTRAL_API_KEY")
    if not key:
        env_file = ROOT / ".env"
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                if k.strip() == "MISTRAL_API_KEY":
                    key = v.strip()
                    break
    if not key:
        raise SystemExit("MISTRAL_API_KEY not found in environment or .env")
    # The agents SDK reads the key from the environment, not from a client arg.
    os.environ["MISTRAL_API_KEY"] = key
    return key


def is_mp3(data: bytes) -> bool:
    return data[:3] == b"ID3" or (len(data) > 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0)


def speak(client, text: str, response_format: str) -> bytes:
    resp = client.audio.speech.complete(
        model=TTS_MODEL,
        input=text,
        voice_id=VOICE_ID,
        response_format=response_format,
    )
    return base64.b64decode(resp.audio_data)


def step_tts_tones(client) -> None:
    print("== TTS: one sentence in each tone ==")
    for tone, tag in TONE_TAGS.items():
        path = ROOT / f"smoke-{tone}.mp3"
        try:
            data = speak(client, tag + REPLY_SENTENCE, "mp3")
            path.write_bytes(data)
            ok = is_mp3(data) and len(data) > 1000
            check(f"tts tone {tone!r}", ok, f"{path.name} {len(data)} bytes, mp3 magic={is_mp3(data)}")
        except Exception as exc:  # noqa: BLE001 - report any API failure
            check(f"tts tone {tone!r}", False, f"{type(exc).__name__}: {exc}")


def step_transcribe(client) -> None:
    print("== Transcription: clip with context_bias ==")
    wav = speak(client, CLIP_SENTENCE, "wav")
    clip_path = ROOT / "smoke-clip.wav"
    clip_path.write_bytes(wav)
    print(f"clip written: {clip_path.name} ({len(wav)} bytes, synthesized with {TTS_MODEL})")
    try:
        res = client.audio.transcriptions.complete(
            model=TRANSCRIBE_MODEL,
            file={"file_name": "smoke-clip.wav", "content": wav},
            language="en",
            context_bias=CONTEXT_BIAS,
        )
        print(f"transcript: {res.text!r}")
        check("transcript contains 'RDL'", "RDL" in res.text.upper(), repr(res.text))
    except Exception as exc:  # noqa: BLE001
        check("transcript contains 'RDL'", False, f"{type(exc).__name__}: {exc}")
    # Non-wav upload: can the endpoint take an mp3 (stands in for the browser's webm/opus)?
    mp3 = speak(client, CLIP_SENTENCE, "mp3")
    try:
        res = client.audio.transcriptions.complete(
            model=TRANSCRIBE_MODEL,
            file={"file_name": "smoke-clip.mp3", "content": mp3},
            language="en",
            context_bias=CONTEXT_BIAS,
        )
        print(f"mp3 transcript: {res.text!r}")
        check("mp3 upload accepted by transcriber", "RDL" in res.text.upper(), repr(res.text))
    except Exception as exc:  # noqa: BLE001
        check("mp3 upload accepted by transcriber", False, f"{type(exc).__name__}: {exc}")


@agents.tool
def ping(note: str) -> str:
    """Test tool: returns 'pong' followed by the note."""
    return f"pong {note}"


def make_agent():
    agent = agents.Agent(
        model=AGENT_MODEL,
        instructions=(
            "You are a smoke-test agent. When the user asks you to ping, call the "
            "ping tool with the note they give, then reply with exactly what the "
            "tool returned."
        ),
        tools=[ping],
    )
    return agent


async def step_agent() -> None:
    agent = make_agent()
    print(f"== Agent on {AGENT_MODEL} with dummy tool 'ping' ==")
    # Agent.run() closes its session when the turn ends, so for a multi-turn
    # session we keep the handle from start_session() (Task 5 rebinds by id).
    session = await agent.start_session()
    first = await session.run("Call the ping tool with note 'first', then reply with its exact result.")
    if not isinstance(first, agents.Completed):
        check("agent turn 1 completed", False, repr(first))
        return
    calls = [c.name for c in first.tool_calls]
    print(f"reply 1: {first.text!r}")
    print(f"tool calls in turn 1: {calls}")
    check("agent turn 1 completed", True, f"session_id={first.session_id}")
    check("dummy tool called in turn 1", any("ping" in name for name in calls), str(calls))

    second = await session.run("Now call the ping tool with note 'second', then reply with its exact result.")
    if not isinstance(second, agents.Completed):
        check("agent turn 2 completed (same session)", False, repr(second))
        return
    calls2 = [c.name for c in second.tool_calls]
    print(f"reply 2: {second.text!r}")
    print(f"tool calls in turn 2: {calls2}")
    check("same session continued", second.session_id == first.session_id,
          f"{second.session_id} == {first.session_id}")
    check("dummy tool called in turn 2", any("ping" in name for name in calls2), str(calls2))

    # Rebind by id inside the same event loop: this is what /api/turn does with
    # the session_id it sends back on the next request.
    rebound = agent.session(first.session_id)
    third = await rebound.run("Call the ping tool with note 'third', then reply with its exact result.")
    if not isinstance(third, agents.Completed):
        check("session rebound by id ran turn 3", False, repr(third))
        return
    print(f"reply 3: {third.text!r}")
    check("session rebound by id ran turn 3",
          third.session_id == first.session_id and any("ping" in c.name for c in third.tool_calls),
          f"session_id={third.session_id}, tool calls={[c.name for c in third.tool_calls]}")


async def main() -> None:
    from mistralai.client import Mistral

    print(f"mistralai=={version('mistralai')}  mistralai-agents=={version('mistralai-agents')}")
    client = Mistral(api_key=load_api_key())
    step_tts_tones(client)
    step_transcribe(client)
    await step_agent()
    print()
    if failures:
        print(f"SMOKE FAIL: {len(failures)} check(s) failed: {', '.join(failures)}")
        sys.exit(1)
    print("SMOKE PASS: all checks passed")


if __name__ == "__main__":
    asyncio.run(main())
