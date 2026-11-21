#!/usr/bin/env python3
"""Task 6 replay: typed-transcript end-to-end checks against a running server.

Run from the repo root with the app up (the tester uses port 8001):

    uv run uvicorn app.main:app --port 8001
    uv run python scripts/replay.py                          # http://127.0.0.1:8001
    uv run python scripts/replay.py --base-url http://127.0.0.1:8000

For each of the eight transcripts in docs/BUILD-BRIEF.md (Task 6) the script
starts a new conversation with POST /api/reset, posts the typed transcript to
POST /api/turn (multipart form, `transcript` field only — the typed test path
from the brief), and checks saves, trace, tone and mood against the "Expect"
column. Transcripts marked "(same conversation)" reuse the `session_id` that
the previous turn returned, exactly like the page does.

One PASS/FAIL line is printed per case, then a total. Exit code is 0 only when
all eight cases pass. A server that cannot be reached is reported as "not run",
never as passed.

The script only speaks HTTP and needs no API key itself (the server does).
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
import uuid

DEFAULT_BASE = "http://127.0.0.1:8001"  # tester port; coders use 8000
TIMEOUT_S = 180  # one turn = agent + TTS, can be slow


class Unreachable(Exception):
    """The server could not be reached at all (report as not run)."""


class Api:
    """Minimal HTTP client for the routes replay needs (stdlib only)."""

    def __init__(self, base: str):
        self.base = base.rstrip("/")

    def _request(self, method: str, path: str, data=None, headers=None):
        req = urllib.request.Request(
            self.base + path, data=data, headers=headers or {}, method=method
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                raw = resp.read().decode("utf-8")
                try:
                    return resp.status, json.loads(raw)
                except json.JSONDecodeError:
                    return resp.status, {"raw": raw}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                return exc.code, json.loads(body)
            except json.JSONDecodeError:
                return exc.code, {"error": f"HTTP {exc.code}", "body": body[:500]}
        except (urllib.error.URLError, OSError) as exc:
            raise Unreachable(f"{method} {path}: {exc}") from exc

    def ping(self):
        """Any HTTP response means the server is up; only connection errors raise."""
        return self._request("GET", "/api/exercises")

    def reset(self):
        return self._request("POST", "/api/reset", data=b"")

    def sessions(self, exercise_id: str, limit: int = 5):
        return self._request(
            "GET", f"/api/sessions?exercise={exercise_id}&limit={limit}"
        )

    def turn(self, transcript: str, session_id: str | None):
        boundary = "voicefit-" + uuid.uuid4().hex
        fields = [("transcript", transcript)]
        if session_id:
            fields.append(("session_id", session_id))
        body = b""
        for name, value in fields:
            body += (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                f"{value}\r\n"
            ).encode("utf-8")
        body += f"--{boundary}--\r\n".encode("utf-8")
        return self._request(
            "POST",
            "/api/turn",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )


# --- response helpers --------------------------------------------------------


def saved(resp: dict) -> list[dict]:
    """Saved sessions of a turn (entries with saved == true)."""
    return [
        s
        for s in (resp.get("saved_sessions") or [])
        if isinstance(s, dict) and s.get("saved")
    ]


def trace_entries(resp: dict, tool: str | None = None) -> list[dict]:
    return [
        t
        for t in (resp.get("trace") or [])
        if isinstance(t, dict) and (tool is None or t.get("tool") == tool)
    ]


def approx(a, b, tol=1e-9) -> bool:
    return isinstance(a, (int, float)) and not isinstance(a, bool) and abs(a - b) <= tol


def summarize(resp: dict) -> str:
    ss = saved(resp)
    parts = [f"{len(ss)} save(s)"]
    for s in ss:
        parts.append(
            f"{s.get('exercise_id')} {s.get('weight_kg')}kg {s.get('reps')} "
            f"{s.get('outcome')} mood={s.get('mood')}"
        )
    parts.append(f"tone={resp.get('tone')} mood={resp.get('mood')}")
    parts.append("trace=" + ",".join(t.get("tool", "?") for t in trace_entries(resp)))
    return "; ".join(parts)


# --- per-case checks (the "Expect" column of Task 6) -------------------------
# Each check returns a list of problem strings; empty means the case passed.


def check_case1(resp, api):
    """RDLs, same weight as last time. Five, five, and five, actually six on the last set."""
    probs = []
    ss = saved(resp)
    if len(ss) != 1:
        return [f"expected 1 save, got {len(ss)}: {ss}"]
    s = ss[0]
    if s.get("exercise_id") != "romanian_deadlift":
        probs.append(f"exercise_id: expected 'romanian_deadlift', got {s.get('exercise_id')!r}")
    if not approx(s.get("weight_kg"), 80.0):
        probs.append(f"weight_kg: expected 80, got {s.get('weight_kg')!r}")
    if s.get("reps") != [5, 5, 6]:
        probs.append(f"reps: expected [5, 5, 6], got {s.get('reps')!r}")
    if s.get("outcome") != "beat":
        probs.append(f"outcome: expected 'beat', got {s.get('outcome')!r}")
    status, rows = api.sessions("romanian_deadlift", limit=1)
    if status != 200:
        probs.append(f"GET /api/sessions -> HTTP {status}: {rows}")
    elif not rows or rows[0].get("id") != s.get("session_id") or rows[0].get("is_seed") not in (0, False):
        probs.append(f"newest RDL via GET /api/sessions is not the saved row: {rows[:1]}")
    return probs


def check_case2(resp, api):
    """I'm feeling low today, what should I do?"""
    probs = []
    if saved(resp):
        probs.append(f"expected 0 saves, got {saved(resp)}")
    if not any(t.get("args", {}).get("mood") == "low" for t in trace_entries(resp, "get_mood_history")):
        probs.append(
            "trace has no get_mood_history with mood='low'; tools="
            f"{[t.get('tool') for t in trace_entries(resp)]}"
        )
    reply = resp.get("reply_text") or ""
    if "romanian deadlift" not in reply.lower():
        probs.append(f"reply does not name Romanian deadlift: {reply!r}")
    if resp.get("tone") != "calm":
        probs.append(f"tone: expected 'calm', got {resp.get('tone')!r}")
    if resp.get("mood") != "low":
        probs.append(f"mood: expected 'low', got {resp.get('mood')!r}")
    return probs


def check_case3(resp, api):
    """(same conversation) RDLs, same as last time, five, five, five."""
    probs = []
    ss = saved(resp)
    if len(ss) != 1:
        return [f"expected 1 save, got {len(ss)}: {ss}"]
    s = ss[0]
    if s.get("exercise_id") != "romanian_deadlift":
        probs.append(f"exercise_id: expected 'romanian_deadlift', got {s.get('exercise_id')!r}")
    if not approx(s.get("weight_kg"), 80.0):
        probs.append(f"weight_kg: expected 80, got {s.get('weight_kg')!r}")
    if s.get("reps") != [5, 5, 5]:
        probs.append(f"reps: expected [5, 5, 5], got {s.get('reps')!r}")
    if s.get("mood") != "low":
        probs.append(f"saved mood: expected 'low', got {s.get('mood')!r}")
    if s.get("outcome") != "held":
        probs.append(f"outcome: expected 'held', got {s.get('outcome')!r}")
    if resp.get("tone") != "calm":
        probs.append(f"tone: expected 'calm', got {resp.get('tone')!r}")
    return probs


def check_case4(resp, api):
    """Bench, 62.5 kilos, eight, seven, seven, and squats same as last time, five, five, five."""
    probs = []
    ss = saved(resp)
    if len(ss) != 2:
        return [f"expected 2 saves, got {len(ss)}: {ss}"]
    by_ex = {s.get("exercise_id"): s for s in ss}
    bench = by_ex.get("bench_press")
    squat = by_ex.get("back_squat")
    if bench is None:
        probs.append(f"no bench_press save in {list(by_ex)}")
    else:
        if not approx(bench.get("weight_kg"), 62.5):
            probs.append(f"bench weight_kg: expected 62.5, got {bench.get('weight_kg')!r}")
        if bench.get("reps") != [8, 7, 7]:
            probs.append(f"bench reps: expected [8, 7, 7], got {bench.get('reps')!r}")
        if bench.get("outcome") != "dropped":
            probs.append(f"bench outcome: expected 'dropped', got {bench.get('outcome')!r}")
    if squat is None:
        probs.append(f"no back_squat save in {list(by_ex)}")
    else:
        if not approx(squat.get("weight_kg"), 102.5):
            probs.append(f"squat weight_kg: expected 102.5, got {squat.get('weight_kg')!r}")
        if squat.get("reps") != [5, 5, 5]:
            probs.append(f"squat reps: expected [5, 5, 5], got {squat.get('reps')!r}")
        if squat.get("outcome") != "held":
            probs.append(f"squat outcome: expected 'held', got {squat.get('outcome')!r}")
    return probs


def check_case5(resp, api):
    """Overhead press, same as last time, five and five."""
    probs = []
    if saved(resp):
        probs.append(f"expected 0 saves, got {saved(resp)}")
    reply = (resp.get("reply_text") or "").lower()
    if "weight" not in reply:
        probs.append(f"reply does not ask for the weight: {resp.get('reply_text')!r}")
    return probs


def check_case6(resp, api):
    """(same conversation) Forty kilos."""
    probs = []
    ss = saved(resp)
    if len(ss) != 1:
        return [f"expected 1 save, got {len(ss)}: {ss}"]
    s = ss[0]
    if s.get("exercise_id") != "overhead_press":
        probs.append(f"exercise_id: expected 'overhead_press', got {s.get('exercise_id')!r}")
    if not approx(s.get("weight_kg"), 40.0):
        probs.append(f"weight_kg: expected 40, got {s.get('weight_kg')!r}")
    if s.get("reps") != [5, 5]:
        probs.append(f"reps: expected [5, 5], got {s.get('reps')!r}")
    if s.get("outcome") != "first":
        probs.append(f"outcome: expected 'first', got {s.get('outcome')!r}")
    return probs


def check_case7(resp, api):
    """Bench, one thirty-five pounds, five, five."""
    probs = []
    ss = saved(resp)
    if len(ss) != 1:
        return [f"expected 1 save, got {len(ss)}: {ss}"]
    s = ss[0]
    if s.get("exercise_id") != "bench_press":
        probs.append(f"exercise_id: expected 'bench_press', got {s.get('exercise_id')!r}")
    if not approx(s.get("weight_kg"), 61.23, tol=0.005):
        probs.append(f"weight_kg: expected 61.23 (135 lb), got {s.get('weight_kg')!r}")
    if s.get("reps") != [5, 5]:
        probs.append(f"reps: expected [5, 5], got {s.get('reps')!r}")
    return probs


# "curls" is not in the vocab: the reply must say the exercise is not known.
_UNKNOWN_REPLY_HINTS = [
    "unknown", "not known", "don't know", "dont know", "not an exercise",
    "no such", "recognis", "recogniz", "not in", "can't", "cannot",
    "isn't", "is not", "no exercise", "don't have", "dont have", "no idea",
]


def check_case8(resp, api):
    """Did some curls, ten, ten, ten."""
    probs = []
    if saved(resp):
        probs.append(f"expected 0 saves, got {saved(resp)}")
    reply = resp.get("reply_text") or ""
    low = reply.lower()
    if "curl" not in low or not any(h in low for h in _UNKNOWN_REPLY_HINTS):
        probs.append(f"reply does not say the exercise is not known: {reply!r}")
    return probs


CASES = [
    {"n": 1, "same_conversation": False, "check": check_case1,
     "transcript": "RDLs, same weight as last time. Five, five, and five, actually six on the last set."},
    {"n": 2, "same_conversation": False, "check": check_case2,
     "transcript": "I'm feeling low today, what should I do?"},
    {"n": 3, "same_conversation": True, "check": check_case3,
     "transcript": "RDLs, same as last time, five, five, five."},
    {"n": 4, "same_conversation": False, "check": check_case4,
     "transcript": "Bench, 62.5 kilos, eight, seven, seven, and squats same as last time, five, five, five."},
    {"n": 5, "same_conversation": False, "check": check_case5,
     "transcript": "Overhead press, same as last time, five and five."},
    {"n": 6, "same_conversation": True, "check": check_case6,
     "transcript": "Forty kilos."},
    {"n": 7, "same_conversation": False, "check": check_case7,
     "transcript": "Bench, one thirty-five pounds, five, five."},
    {"n": 8, "same_conversation": False, "check": check_case8,
     "transcript": "Did some curls, ten, ten, ten."},
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--base-url",
        default=os.environ.get("VOICEFIT_BASE_URL", DEFAULT_BASE),
        help=f"server base URL (default: {DEFAULT_BASE})",
    )
    args = parser.parse_args()
    api = Api(args.base_url)
    print(f"replay against {api.base}")

    try:
        api.ping()
    except Unreachable as exc:
        print(f"REPLAY: not run — cannot reach {api.base}: {exc}")
        print("start the server first, e.g.  uv run uvicorn app.main:app --port 8001")
        return 2

    session_id = None
    passed = 0
    not_run = 0
    for case in CASES:
        n = case["n"]
        label = "same conversation, " if case["same_conversation"] else ""
        try:
            if not case["same_conversation"]:
                status, body = api.reset()
                if status != 200:
                    print(f"case {n} FAIL — {label}POST /api/reset -> HTTP {status}: {body}")
                    continue
                session_id = None
            status, resp = api.turn(case["transcript"], session_id)
        except Unreachable as exc:
            print(f"case {n} NOT RUN — {label}{exc}")
            not_run += 1
            for rest in CASES:  # the remaining cases cannot run either
                if rest["n"] > n:
                    print(f"case {rest['n']} NOT RUN — server unreachable")
                    not_run += 1
            break
        if status != 200:
            print(f"case {n} FAIL — {label}POST /api/turn -> HTTP {status}: {resp}")
            continue
        session_id = resp.get("session_id")
        problems = case["check"](resp, api)
        if problems:
            print(f"case {n} FAIL — {label}{case['transcript']}")
            for p in problems:
                print(f"    - {p}")
            print(f"    got: {summarize(resp)}")
        else:
            passed += 1
            print(f"case {n} PASS — {label}{case['transcript']}")
            print(f"    {summarize(resp)}")

    total = len(CASES)
    ran = total - not_run
    print()
    if not_run:
        print(f"REPLAY: {passed}/{ran} passed, {not_run} not run (server unreachable)")
        return 2
    print(f"REPLAY: {passed}/{total} passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
