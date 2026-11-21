# VoiceFit — Task Board

Owned by the coordinator. Updated after every assignment, verdict and merge. This file is the single record of where the build stands.

**Clock start:** _(coordinator fills in, London time)_
**Feature freeze:** clock start + 3:10
**Submission deadline:** 18:00 London time

## Tasks

Status values: `todo`, `in progress`, `in review`, `changes requested`, `merged`, `cut`.

| # | Task | Lane | Depends on | Target finish | Status | PR | Review | Test |
|---|---|---|---|---|---|---|---|---|
| 0 | Prove the API, write `NOTES.md` | core | — | 0:25 | todo | | | |
| 1 | Database and seed | core | — | 0:45 | todo | | | |
| 2 | Tools and comparison rule | core | 1 | 1:10 | todo | | | |
| 3 | Voice: transcribe and speak | core | 0 | 1:30 | todo | | | |
| 4 | Page against the mock | ui | — | 1:30 | todo | | | |
| 5 | Agent and `/api/turn` | core | 0, 2, 3 | 2:30 | todo | | | |
| 6 | Replay tests and hardening | core | 5 | 3:10 | todo | | | |
| T1 | Tests for Tasks 1 and 2 from the contracts | tester | — | 0:30 | todo | | | |
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

_(coordinator lists anything an agent is blocked on that only a person can do)_
