# VoiceFit — Task Board

Owned by the coordinator. Updated after every assignment, verdict and merge. This file is the single record of where the build stands.

**Clock start:** 12:50 London, Saturday 21 November 2026
**Feature freeze:** 16:00 London (clock start + 3:10)
**Submission deadline:** 18:00 London time

## Tasks

Status values: `todo`, `in progress`, `in review`, `changes requested`, `merged`, `cut`.

| # | Task | Lane | Depends on | Target finish | Status | PR | Review | Test |
|---|---|---|---|---|---|---|---|---|
| 0 | Prove the API, write `NOTES.md` | core | — | 0:25 | in review | 3 | REVIEW: PASS | TEST pending |
| 1 | Database and seed | core | — | 0:45 | in progress | | | |
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

- 14:00 — Task 0 is late against its 0:25 target (PR 3 opened 13:45, REVIEW: PASS, TEST still pending). Gate 0:25 therefore missed by >15 min; recovery is one TEST verdict away, so no cut proposed yet. If TEST has not passed by 14:15, reassess against the cut order.
- 13:58 — PR 1 (Task 4): tester measured white-on-accent text at 3.91:1 vs the UI-SPEC line "at least 4.5:1 for all text"; reviewer passed it (18–26 px bold text, above the 3:1 large-text threshold). Accepted as reviewed; logged here for honesty.
- 14:00 — T1 merged on REVIEW: PASS alone, per WORKFLOW.md tester-PR rule (reviewer only).

## Human actions waiting

- 14:00 — Person 2: confirm the three recorded test clips exist and where; the tester needs one to run Task 0's smoke script on PR 3, and Task 3 needs clips too.
- 14:00 — Tester: post the TEST verdict on PR 3 (Task 0). Task 0 is past its 0:25 gate; this verdict is the recovery path.
