# VoiceFit — Task Board

Owned by the coordinator. Updated after every assignment, verdict and merge. This file is the single record of where the build stands.

**Clock start:** 12:50 London, Saturday 21 November 2026
**Feature freeze:** 16:00 London (clock start + 3:10)
**Submission deadline:** 18:00 London time

## Tasks

Status values: `todo`, `in progress`, `in review`, `changes requested`, `merged`, `cut`.

| # | Task | Lane | Depends on | Target finish | Status | PR | Review | Test |
|---|---|---|---|---|---|---|---|---|
| 0 | Prove the API, write `NOTES.md` | core | — | 0:25 | in progress | | | |
| 1 | Database and seed | core | — | 0:45 | todo | | | |
| 2 | Tools and comparison rule | core | 1 | 1:10 | todo | | | |
| 3 | Voice: transcribe and speak | core | 0 | 1:30 | todo | | | |
| 4 | Page against the mock | ui | — | 1:30 | in progress | | | |
| 5 | Agent and `/api/turn` | core | 0, 2, 3 | 2:30 | todo | | | |
| 6 | Replay tests and hardening | core | 5 | 3:10 | todo | | | |
| T1 | Tests for Tasks 1 and 2 from the contracts | tester | — | 0:30 | in progress | | | |
| T2 | `scripts/replay.py` | tester | — | 1:30 | todo | | | |

Task 1 does not need Task 0, so if Task 0 is waiting on a human (key, clip), the core coder starts Task 1.

## Gates

| Time | Gate | Met? |
|---|---|---|
| 0:25 | `NOTES.md` has working model IDs and parameter names | |
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

_(coordinator logs anything that departs from the brief, with the time and the reason)_

## Human actions waiting

- 12:50 — Person 2: record the three test clips (per PLAN.md 0:00–0:25) so Task 0 and Task 3 have audio. Task 0 is blocked without a clip.
- 12:50 — Both people: open the four agent sessions in their worktrees (`voicefit-wt/coder`, `coder-ui`, `reviewer`, `tester`) with the first-message script from `docs/WORKFLOW.md`; coordinator assigns Task 0 to core coder, Task 4 to ui coder, T1 to tester.
