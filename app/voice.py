"""Voice for VoiceFit (Task 3): transcribe() and speak().

Every model ID, parameter name and voice comes from NOTES.md (verified
against the live API in Task 0) — not from memory.

- transcribe(audio_bytes, filename) -> str
  File transcription, model voxtral-mini-transcribe-3-0, with context_bias
  set from vocab.context_bias_terms().
- speak(text, tone) -> (bytes, mime)
  Model voxtral-mini-tts-3-0, one preset voice (voice_478), mp3 output.
  tone in {pleased, calm, neutral} maps to inline emotion/pace tags in the
  input text (Voxtral 3 style); neutral uses no tag.

The API key lives in .env as MISTRAL_API_KEY and is never printed or logged.
"""

import base64
import os
from pathlib import Path

from mistralai.client import Mistral

from .vocab import context_bias_terms

# From NOTES.md (Task 0, verified live):
TRANSCRIBE_MODEL = "voxtral-mini-transcribe-3-0"
TTS_MODEL = "voxtral-mini-tts-3-0"
VOICE_ID = "voice_478"  # preset en_us voice, kind pvc

# Tone -> inline tags prepended to the input (docs: Emotion and pace tags).
# Invalid tag values are silently ignored by the API, so only use listed ones.
TONE_TAGS = {
    "pleased": "[emotion=happy]",
    "calm": "[emotion=calm][pace=slow]",
    "neutral": "",
}

MP3_MIME = "audio/mpeg"

_client: Mistral | None = None


def load_api_key() -> str:
    """MISTRAL_API_KEY from the environment or from .env at the repo root.

    Also sets os.environ so the agents SDK (Task 5) finds it. Never printed.
    """
    key = os.environ.get("MISTRAL_API_KEY", "").strip()
    if not key:
        env_file = Path(__file__).resolve().parent.parent / ".env"
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                if k.strip() == "MISTRAL_API_KEY" and v.strip():
                    key = v.strip()
                    break
    if not key:
        raise RuntimeError("MISTRAL_API_KEY is not set (environment or .env)")
    os.environ["MISTRAL_API_KEY"] = key
    return key


def _get_client() -> Mistral:
    global _client
    if _client is None:
        _client = Mistral(api_key=load_api_key())
    return _client


def transcribe(audio_bytes: bytes, filename: str) -> str:
    """Transcribe an audio file (wav/mp3/webm...) to text with context bias."""
    client = _get_client()
    res = client.audio.transcriptions.complete(
        model=TRANSCRIBE_MODEL,
        file={"file_name": filename, "content": audio_bytes},
        context_bias=context_bias_terms(),
    )
    return res.text


def speak(text: str, tone: str) -> tuple[bytes, str]:
    """Speak text in the given tone; returns (mp3 bytes, mime)."""
    client = _get_client()
    tag = TONE_TAGS.get(tone, TONE_TAGS["neutral"])
    resp = client.audio.speech.complete(
        model=TTS_MODEL,
        input=tag + text,
        voice_id=VOICE_ID,
        response_format="mp3",
    )
    return base64.b64decode(resp.audio_data), MP3_MIME
