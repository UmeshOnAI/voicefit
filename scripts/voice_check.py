#!/usr/bin/env python3
"""Task 3 check: app/voice.py transcribes a clip and speaks all three tones.

Run from the repo root:

    uv run python scripts/voice_check.py

1. Speaks (synthesizes) a clip saying "RDLs, eighty kilos, five, five, six"
   with voice.speak, writes voice-check-clip.mp3 (no microphone here).
2. Transcribes it back with voice.transcribe (context_bias from vocab) and
   requires the transcript to contain "RDL".
3. Produces voice-check-{pleased,calm,neutral}.mp3 with voice.speak and
   validates each file as mp3 (ID3 header or frame sync).

Exit code 1 if any check fails. Artifacts are gitignored (voice-check-*.mp3).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import voice  # noqa: E402

CLIP_SENTENCE = "RDLs, eighty kilos, five, five, six."
REPLY_SENTENCE = "Logged. Sixteen reps at eighty kilos. That is one more than last time."

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))
    if not ok:
        failures.append(name)


def is_mp3(data: bytes) -> bool:
    return data[:3] == b"ID3" or (len(data) > 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0)


def main() -> None:
    voice.load_api_key()

    print("== speak: synthesize the clip, then transcribe it back ==")
    clip, mime = voice.speak(CLIP_SENTENCE, "neutral")
    clip_path = ROOT / "voice-check-clip.mp3"
    clip_path.write_bytes(clip)
    check("clip synthesized (mp3)", is_mp3(clip) and mime == "audio/mpeg",
          f"{clip_path.name} {len(clip)} bytes mime={mime}")

    text = voice.transcribe(clip, clip_path.name)
    print(f"transcript: {text!r}")
    check("transcript contains 'RDL'", "RDL" in text.upper(), repr(text))

    print("== speak: one sentence in each tone ==")
    for tone in ("pleased", "calm", "neutral"):
        data, mime = voice.speak(REPLY_SENTENCE, tone)
        path = ROOT / f"voice-check-{tone}.mp3"
        path.write_bytes(data)
        check(f"tone {tone!r}", is_mp3(data) and len(data) > 1000 and mime == "audio/mpeg",
              f"{path.name} {len(data)} bytes")

    print()
    if failures:
        print(f"VOICE CHECK FAIL: {', '.join(failures)}")
        sys.exit(1)
    print("VOICE CHECK PASS: all checks passed")


if __name__ == "__main__":
    main()
