# VoiceFit — Instructions for Every Agent

VoiceFit is a voice-first workout logger built for the Mistral Le Chonk London hackathon. A lifter speaks; Voxtral 3 transcribes; a Mistral Agent on Mistral Large 4 looks up and saves sessions through three tools; Voxtral 3 speaks the reply.

The build has a hard deadline today. Do exactly what the specification says, no more.

## Your role

Your first message names your role: **coordinator**, **coder**, **reviewer** or **tester**. Read `docs/agents/<role>.md` and follow it. If no role was given, ask before doing anything.

## Read before you act

| Document | What it is | Who reads it |
|---|---|---|
| `docs/BUILD-BRIEF.md` | Technical specification, contracts, tasks | Everyone |
| `docs/UI-SPEC.md` | The page: wireframe, elements, states | Ui coder, reviewer, tester |
| `docs/WORKFLOW.md` | Worktrees, branches, pull requests | Everyone |
| `docs/TASKS.md` | Live task board | Everyone reads; coordinator writes |
| `docs/PLAN.md` | Why the product is shaped this way, demo script | Coordinator |
| `NOTES.md` | Verified Mistral model IDs and parameter names (created by Task 0) | Anyone calling the Mistral API |

## Rules that apply to everyone

1. **Work only in your own worktree and your own files.** See `docs/WORKFLOW.md`.
2. **All code reaches `main` through a pull request.** No direct commits to `main`, except the coordinator updating `docs/TASKS.md`.
3. **Mistral names come from `NOTES.md`, not from memory or from the brief.** If a name is not there, stop and ask.
4. **The model never does arithmetic.** Totals, comparisons and counts are computed in `app/tools.py`.
5. **Never guess a weight or a unit.**
6. **Never print, log or commit the API key.** It lives in `.env`, which is ignored by git.
7. **No scope beyond the brief.** No charts, calendar, authentication, extra tools or extra dependencies.
8. **If the specification cannot work as written, stop and tell the coordinator.** Do not invent a workaround.
9. **Report what you actually ran and saw.** A check you did not run is "not run", never "passed".

## Commands

```
uv sync                                  install dependencies
uv run pytest -q                         unit tests
uv run uvicorn app.main:app --port 8000  run the app (tester uses 8001)
uv run python scripts/smoke.py           Task 0 API check
uv run python scripts/replay.py          typed-transcript replay tests
```
