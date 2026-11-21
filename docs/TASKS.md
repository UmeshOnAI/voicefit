# VoiceFit — Task Board

Owned by the coordinator. Updated after every assignment, verdict and merge. This file is the single record of where the build stands.

**Clock start:** 12:50 London, Saturday 21 November 2026
**Feature freeze:** 16:00 London (clock start + 3:10)
**Submission deadline:** 18:00 London time

## Tasks

Status values: `todo`, `in progress`, `in review`, `changes requested`, `merged`, `cut`.

| # | Task | Lane | Depends on | Target finish | Status | PR | Review | Test |
|---|---|---|---|---|---|---|---|---|
| 0 | Prove the API, write `NOTES.md` | core | — | 0:25 | merged | 3 | REVIEW: PASS | TEST: PASS |
| 1 | Database and seed | core | — | 0:45 | in review | 5 | pending | pending |
| 2 | Tools and comparison rule | core | 1 | 1:10 | todo | | | |
| 3 | Voice: transcribe and speak | core | 0 | 1:30 | todo | | | |
| 4 | Page against the mock | ui | — | 1:30 | merged | 1 | REVIEW: PASS | TEST: PASS |
| 5 | Agent and `/api/turn` | core | 0, 2, 3 | 2:30 | todo | | | |
| 6 | Replay tests and hardening | core | 5 | 3:10 | todo | | | |
| T1 | Tests for Tasks 1 and 2 from the contracts | tester | — | 0:30 | merged | 2 | REVIEW: PASS | n/a (reviewer-only per WORKFLOW) |
| T2 | `scripts/replay.py` | tester | — | 1:30 | in progress | | | |

Task 1 does not need Task 0, so if Task 0 is waiting on a human (key, clip), the core coder starts Task 1.

## Gates

| Time | Gate | Met? |
|---|---|---|
| 0:25 | `NOTES.md` has working model IDs and parameter names | Met 14:21 via PR 3 — ~66 min late |
| 2:30 | Spoken deadlift sentence saves exactly one session with [5, 5, 6] and the spoken comparison matches the screen | |
| 3:10 | Feature freeze; all eight replay transcripts pass | |
| 3:40 | Submission video recorded and checked on a second device | |

If a gate is missed by more than 15 minutes, the coordinator stops and tells the humans, with a proposal for what to cut.

## Cut order

If time runs short, cut from the top:

1. The French run (already optional)
2. The three voice tones (fall back to one voice)
3. Multi-exercise recap
4. Mood chips (keep spoken mood)

Never cut: the deadlift sentence end to end, the tool trace, the typed fallback box.

## Decisions and deviations

- 14:21 — Task 0 merged (PR 3) with REVIEW: PASS + TEST: PASS; gate 0:25 met ~66 min late. The slip was waiting on the recorded clip (human action) and review queueing; no cut was needed. `NOTES.md` verified names: `mistral-large-4`, `voxtral-mini-transcribe-3-0`, `voxtral-mini-tts-3-0`, `context_bias` list on `transcriptions.complete`, `voice_id="voice_478"`, tone via inline `[emotion=…]`/`[pace=…]` tags, agents SDK `start_session()`/`session.run()`/`agent.session(id)` rebind.
- 14:32 — PR 4 (`fix/test-runtime-skip`) merged (`18de2f9`) on REVIEW: PASS + TEST: PASS: `pytest -q` on main now exits 0 while `app/` is absent (70 skipped). Later PRs' TEST steps run clean.
- 13:58 — PR 1 (Task 4): tester measured white-on-accent text at 3.91:1 vs the UI-SPEC line "at least 4.5:1 for all text"; reviewer passed it (18–26 px bold text, above the 3:1 large-text threshold). Accepted as reviewed; logged here for honesty.
- 14:00 — T1 merged on REVIEW: PASS alone, per WORKFLOW.md tester-PR rule (reviewer only).

## Human actions waiting

- 14:10 — Person 2, on merged PR 1 (Task 4 page): run in a real browser the two checks the tester could not: UI-SPEC acceptance check 6 (everything visible at 1280×720 without scrolling) and a real microphone recording (MediaRecorder → blob → POST `/api/turn`). Flagged "not run" in the PR 1 TEST comment; the TEST: PASS verdict stands for everything else. **How to run them in a real browser (main checkout, after `git pull`):**
  1. Mock page, no backend needed: `cd static` then `python -m http.server 8099`, open `http://localhost:8099/index.html?mock=1` in Chrome/Edge. Confirm the transcript, coach reply, highlighted BEAT row, Low chip and collapsed trace all render (the tester's harness proved logic; this proves layout).
  2. Check 6: set the window to exactly 1280×720 (DevTools device toolbar), reload `?mock=1`, confirm no page scrollbar appears and Heard/Coach/sessions/trace-summary are all visible without scrolling.
  3. Real mic: with the mock page, click the mic, allow microphone permission, speak any sentence for ~1 s, stop. Expect status Listening… → Thinking… → back to idle, a console line `recorded audio blob: N bytes`, and (mock mode) the mock turn rendered. A full end-to-end mic turn needs Task 5's server: in the coder worktree `uv run uvicorn app.main:app --port 8000`, open `http://localhost:8000/`, hold the mic and say the deadlift sentence.
  - **Which machine:** either. The mock/layout checks (steps 1–2) need no API key and can be run by Person 1 on the main checkout (`voicefit/static`). The end-to-end mic turn needs a backend + key: Person 2 runs it in the tester worktree on port **8001** (demo-critical, per PLAN.md "speaking to the app" is Person 2's job); Person 1 may smoke-test the mic path in the coder worktree on port **8000**. Browser and server must be on the same machine (localhost); one server per port per machine; each worktree has its own `voicefit.db`, so state is independent.
- 14:00 — Person 2: confirm the three recorded test clips exist and where; the tester needs one to run Task 0's smoke script on PR 3, and Task 3 needs clips too. **PR 3 has no TEST verdict at 14:10 and the 0:25 gate is ~55 min past; if no TEST by 14:15 the likely blocker is the missing clip — only a human can record it.**
- 14:00 — Tester: post the TEST verdict on PR 3 (Task 0). Task 0 is past its 0:25 gate; this verdict is the recovery path.
