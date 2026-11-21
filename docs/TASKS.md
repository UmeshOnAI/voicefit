# VoiceFit — Task Board

Owned by the coordinator. Updated after every assignment, verdict and merge. This file is the single record of where the build stands.

**Clock start:** 12:50 London, Saturday 21 November 2026
**Feature freeze:** 16:30 London (moved from 16:00 at 15:38 — see decisions)
**Submission deadline:** 18:00 London time (extended again by the humans at 16:38; was 17:30 from 15:38, originally 18:00)

## Tasks

Status values: `todo`, `in progress`, `in review`, `changes requested`, `merged`, `cut`.

| # | Task | Lane | Depends on | Target finish | Status | PR | Review | Test |
|---|---|---|---|---|---|---|---|---|
| 0 | Prove the API, write `NOTES.md` | core | — | 0:25 | merged | 3 | REVIEW: PASS | TEST: PASS |
| 1 | Database and seed | core | — | 0:45 | merged | 5 | REVIEW: PASS | TEST: PASS |
| 2 | Tools and comparison rule | core | 1 | 1:10 | merged | 6 | REVIEW: PASS | TEST: PASS |
| 3 | Voice: transcribe and speak | core | 0 | 1:30 | merged | 7 | REVIEW: PASS | TEST: PASS |
| 4 | Page against the mock | ui | — | 1:30 | merged | 1 | REVIEW: PASS | TEST: PASS |
| 5 | Agent and `/api/turn` | core | 0, 2, 3 | 2:30 | merged | 9 | REVIEW: PASS (round 2) | TEST: PASS (round 2, after one fix) |
| 6 | Replay tests and hardening | core | 5 | 3:10 | merged | 10 | REVIEW: PASS | TEST: PASS |
| T1 | Tests for Tasks 1 and 2 from the contracts | tester | — | 0:30 | merged | 2 | REVIEW: PASS | n/a (reviewer-only per WORKFLOW) |
| T2 | `scripts/replay.py` | tester | — | 1:30 | merged | 8 | REVIEW: PASS | n/a (reviewer-only per WORKFLOW) |

Task 1 does not need Task 0, so if Task 0 is waiting on a human (key, clip), the core coder starts Task 1.

## Gates

| Time | Gate | Met? |
|---|---|---|
| 0:25 | `NOTES.md` has working model IDs and parameter names | Met 14:21 via PR 3 — ~66 min late |
| 2:30 | Spoken deadlift sentence saves exactly one session with [5, 5, 6] and the spoken comparison matches the screen | **Missed at 15:20; recovered 16:33 on main** — coordinator ran it live on port 8000: exactly 1 save, `romanian_deadlift` 80.0 kg [5,5,6] total 16, outcome `beat` delta +1, tone `pleased`, audio present, trace `get_last_session → log_session`, reply "…16 total reps, one more than last time." |
| 3:10 → 16:30 | Feature freeze (moved from 16:00); all eight replay transcripts pass | **Met** — Task 5 merged 16:30 (`3bf3bfe`); replay **8/8 PASS** at 16:33 (coordinator, main, port 8000) and re-confirmed 17:22 (tester, PR 10, port 8001); pytest 99 passed. Task 6 remainder merged as PR 10 (`ba5502a`): variations **36/40 (90%)**, 4 failures reported honestly in README, not fixed per freeze ruling |
| 3:40 → 17:00 | Submission video recorded and checked on a second device | Open at 17:23 — needs Person 2's status now |

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

- 17:23 — **Person 2, urgent:** video gate 17:00 has passed — confirm the submission video is recorded (mood question, deadlift moment, changed number, trace, recap, no-history question), audio checked on a second device, and submission lands before **18:00** (37 min). This is the only remaining gate.
- 17:25 — Coordinator started the app for browser testing: `uv run uvicorn app.main:app --port 8000` in the main checkout (process running), DB reset to seed at 17:25 (latest RDL seed 80 kg [5,5,5]). Person 1: open `http://localhost:8000/` in a browser on this machine; the Reset demo button restores the seed at any time.
- Optional, only if everything above is done early: PLAN.md fifth-hour activity — five unfamiliar utterances from people outside the team, report the real result to the jury.
- 14:10 — Person 2, on merged PR 1 (Task 4 page): run in a real browser the two checks the tester could not: UI-SPEC acceptance check 6 (everything visible at 1280×720 without scrolling) and a real microphone recording (MediaRecorder → blob → POST `/api/turn`). Flagged "not run" in the PR 1 TEST comment; the TEST: PASS verdict stands for everything else. **How to run them in a real browser (main checkout, after `git pull`):**
  1. Mock page, no backend needed: `cd static` then `python -m http.server 8099`, open `http://localhost:8099/index.html?mock=1` in Chrome/Edge. Confirm the transcript, coach reply, highlighted BEAT row, Low chip and collapsed trace all render (the tester's harness proved logic; this proves layout).
  2. Check 6: set the window to exactly 1280×720 (DevTools device toolbar), reload `?mock=1`, confirm no page scrollbar appears and Heard/Coach/sessions/trace-summary are all visible without scrolling.
  3. Real mic: with the mock page, click the mic, allow microphone permission, speak any sentence for ~1 s, stop. Expect status Listening… → Thinking… → back to idle, a console line `recorded audio blob: N bytes`, and (mock mode) the mock turn rendered. A full end-to-end mic turn needs Task 5's server: in the coder worktree `uv run uvicorn app.main:app --port 8000`, open `http://localhost:8000/`, hold the mic and say the deadlift sentence.
  - **Which machine:** either. The mock/layout checks (steps 1–2) need no API key and can be run by Person 1 on the main checkout (`voicefit/static`). The end-to-end mic turn needs a backend + key: Person 2 runs it in the tester worktree on port **8001** (demo-critical, per PLAN.md "speaking to the app" is Person 2's job); Person 1 may smoke-test the mic path in the coder worktree on port **8000**. Browser and server must be on the same machine (localhost); one server per port per machine; each worktree has its own `voicefit.db`, so state is independent.
- 14:41 — Person 1 browser run, all three human checks now DONE: mock page renders **PASS** (14:41); UI-SPEC check 6, 1280×720 no-scroll **PASS** (~15:00); real mic **PASS** (~15:00) — second click → `Thinking…`, console `recorded audio blob: N bytes, X ms`, mock turn rendered. (The 14:41 "no Thinking…" observation was the expected first-click-only state; `Thinking…` appears on the second click or the 30 s auto-stop per `static/app.js`; <500 ms recordings are silently discarded, app.js:213.) Remaining human-only check: the end-to-end mic turn once Task 5 merges.
- 14:50 — Task 1 merged (PR 5, `a183c5f`) on REVIEW: PASS + TEST: PASS, ~75 min past its 0:45 target (review queueing after the Task 0 clip wait). Task 2 assigned to the core coder at 14:50.
- 15:11 — Task 2 merged (PR 6, `cd00518`) on REVIEW: PASS + TEST: PASS. Task 3 assigned to the core coder at 15:11.
- 15:38 — Humans extended the submission deadline to **17:30 London**. Coordinator decision, same minute: feature freeze moves 16:00 → **16:30** and the video gate 16:30 → **17:00**, keeping 30 min for submission. Clock start unchanged (12:50).
- 16:38 — Humans extended the submission deadline again, to **18:00 London**. Freeze stays at **16:30** (already passed): the extra 30 min buy video/submission/README buffer only — per the freeze rule, no new features, only `fix/` branches. Video gate stays at 17:00 to preserve buffer.
- 16:40 — Scope question from the humans: "can we add features if time remains?" **No.** AGENTS.md rule 7 and the coordinator role refuse anything beyond the brief, and the 16:30 freeze has passed — only `fix/` branches. The only sanctioned extra with spare time is the PLAN's fifth-hour activity: five unfamiliar utterances from people outside the team, reported honestly to the jury — an evaluation, not an app change.
- 16:41 — Task 6 remainder assigned to the core coder as `fix/task6-variations-readme` (variations + README only; no `app/`/`static/` behavior changes). Coordinator's port-8000 verification server in the main checkout was stopped at 16:41 so the coder owns port 8000.
- 17:23 — PR 10 merged (`ba5502a`, README-only): replay 8/8, variations 36/40 (90%) with the 4 failures written honestly into README.md (two kind-1 paraphrases saved [5,5,5,6] instead of [5,5,6]; tersest kind-6 "Forty." saved nothing; one kind-8 variation asked for weight without a tool call). Not fixed — freeze scope, and the brief only requires reporting the pass rate. **All nine task rows are now `merged`; the build is code-complete.** Remaining: human-only video/submission before 18:00.
- 15:38 — Gate 2:30 formally **missed by >15 min** (Task 5 unmerged at 15:38). Per the rules the cut order is now armed: French run is already optional and effectively out; next cuts in order are the three voice tones (fall back to one voice) and multi-exercise recap — to be applied only if Task 5 or Task 6 threatens the 16:30 freeze. Never-cut list stands.
- 15:37 — Task 3 merged (PR 7, `02316a3`) on REVIEW: PASS + TEST: PASS (pytest 88 passed). Task 5 assigned to the core coder at 15:38 — all its dependencies (0, 2, 3) are merged.
- 16:33 — PR 8 (T2, `scripts/replay.py`) merged `199f72c` on REVIEW: PASS. PR 9 (Task 5, `app/main.py` + `app/agent.py`) merged `3bf3bfe` after one fix round (TEST: FAIL → coder fix `8c69a6f` → REVIEW: PASS + TEST: PASS; within the two-round limit). Coordinator verified the 2:30-gate scenario live on main (see gates) and ran `scripts/replay.py` → **8/8 PASS** at 16:33. A server is left running on port 8000 in the main checkout for the end-to-end browser mic test.
- 14:00 — Person 2: confirm the three recorded test clips exist and where; the tester needs one to run Task 0's smoke script on PR 3, and Task 3 needs clips too. **PR 3 has no TEST verdict at 14:10 and the 0:25 gate is ~55 min past; if no TEST by 14:15 the likely blocker is the missing clip — only a human can record it.**
- 14:00 — Tester: post the TEST verdict on PR 3 (Task 0). Task 0 is past its 0:25 gate; this verdict is the recovery path.
