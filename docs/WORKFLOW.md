# VoiceFit — Worktrees and Pull Requests

Every agent works in its own git worktree. All code reaches `main` through a pull request on the GitHub repository. Nobody commits code directly to `main`.

## Layout on each machine

```
voicefit/                 main checkout   — coordinator (always on main)
voicefit-wt/coder/        worktree        — core coder
voicefit-wt/coder-ui/     worktree        — ui coder
voicefit-wt/reviewer/     worktree        — reviewer
voicefit-wt/tester/       worktree        — tester
```

`voicefit-wt` sits next to `voicefit`, not inside it. Each worktree has its own `.env`, its own `.venv` and its own `voicefit.db`; none of these are committed or shared.

## One-time setup (each person, once)

Requirements: `git`, the GitHub CLI `gh` (logged in with `gh auth login`), `uv`, and Mistral Vibe.

On Windows, per the Vibe docs as read on 21 November 2026:

```
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
uv tool install --python 3.14 mistral-vibe
winget install GitHub.cli
```

Open a new terminal after installing `uv`. When Vibe first opens a folder it asks whether to trust it; say yes for `voicefit` and each worktree, otherwise it ignores `AGENTS.md` and project settings. Check that Vibe's active model is Mistral Large 4 (`/config`).

```
git clone <repository URL> voicefit
cd voicefit
```

Then create the worktrees:

- PowerShell: `./scripts/setup-worktrees.ps1`
- bash (WSL, macOS, Linux): `./scripts/setup-worktrees.sh`

Then copy `.env.example` to `.env` in each worktree that runs code (`coder`, `tester`) and put the API key in it.

Person 1 needs `coder`. Person 2 needs `coder-ui`, `reviewer` and `tester`. The script creates all four; unused ones do no harm.

## Starting an agent

Open a terminal **in that agent's worktree folder** and start Vibe there. First message:

> Read `AGENTS.md`. Your role is **<coordinator | coder | reviewer | tester>**. Read `docs/agents/<role>.md` and follow it.

For the core coder add "Your lane is core." For the ui coder add "Your lane is ui."

Each agent is a separate Vibe session in a separate folder. Do not run the coder, reviewer and tester as subagents of the coordinator: Vibe subagents return text only and work in their parent's folder, which defeats the separate worktrees.

Optional: Vibe supports named agents (`.vibe/agents/<name>.toml`, launched with `vibe --agent <name>`). The role files in `docs/agents/` can be wired in that way, but the first-message method above needs no configuration and is the one this project uses.

## Branch names

| Who | Branch | Example |
|---|---|---|
| Coder | `task/<number>-<slug>` | `task/2-tools` |
| Tester (own test code) | `test/<slug>` | `test/tools-contract` |
| Fix after merge | `fix/<slug>` | `fix/lb-rounding` |

One task, one branch, one pull request. Keep a pull request under about 300 changed lines; if a task is larger, split it and tell the coordinator.

## The loop for one task

**1. Coordinator** (in `voicefit/`) picks the next task from `docs/TASKS.md`, marks it `in progress`, and tells the coder which task to do.

**2. Coder** (in its worktree):

```
git fetch origin
git switch -c task/2-tools origin/main
# ... do the task, run its checks ...
git add -A
git commit -m "Task 2: tools and comparison rule"
git push -u origin task/2-tools
gh pr create --base main --title "Task 2: tools" --body-file pr-body.md
```

The pull request body states: the task number, the files changed, each "Done when" check from the brief with the command run and its output, and anything that deviates from the brief. Do not commit `pr-body.md`.

**3. Reviewer** (in its worktree):

```
git fetch origin
gh pr checkout <number> --detach
gh pr diff <number>
```

Reads the diff against `docs/BUILD-BRIEF.md` (and `docs/UI-SPEC.md` for ui work), then posts exactly one verdict comment:

```
gh pr comment <number> --body "REVIEW: PASS"
gh pr comment <number> --body "REVIEW: CHANGES — <numbered list, file and line>"
```

**4. Tester** (in its worktree), at the same time as the reviewer:

```
git fetch origin
gh pr checkout <number> --detach
uv sync
uv run pytest -q
# plus the task's own "Done when" checks
gh pr comment <number> --body "TEST: PASS — <commands and results>"
gh pr comment <number> --body "TEST: FAIL — <command, expected, actual>"
```

If the tester needs a running server, it uses port 8001; coders use port 8000.

**5. Coder** fixes anything raised, on the same branch, and pushes again. The reviewer and tester re-check and post a new verdict.

**6. Coordinator** merges when the latest verdicts are `REVIEW: PASS` and `TEST: PASS`:

```
gh pr merge <number> --squash --delete-branch
git pull
```

Then updates `docs/TASKS.md` and assigns the next task.

Verdicts are comments, not GitHub approvals, because GitHub does not let an account approve its own pull request and the agents share their operator's account.

## Rules

- **Stay in your files.** Core lane: `app/`, `scripts/`, `tests/`, `pyproject.toml`, `NOTES.md`. Ui lane: `static/`. A pull request that touches another lane's files is sent back.
- **Start every branch from fresh `origin/main`.** If `main` moves while a pull request is open and there is a conflict, the coder runs `git fetch origin && git rebase origin/main`, resolves it, and pushes with `git push --force-with-lease`.
- **Never force-push `main`. Never rewrite another agent's branch.**
- **The coordinator may push directly to `main` only for `docs/TASKS.md`.** Everything else goes through a pull request.
- **Two review rounds at most.** If a pull request is not passing after the second round, the coordinator decides: merge with a note in `docs/TASKS.md`, or cut the scope.
- **Review and test inside five minutes** of a pull request opening. The clock matters more than polish.
- **Never commit `.env`, a database file, or generated audio.**
- **After feature freeze (3:10)** only `fix/` branches are opened.

## Tester's own pull requests

The tester writes tests from the contracts in the brief before the code exists, on `test/<slug>` branches. Those pull requests are reviewed by the reviewer only and merged by the coordinator. Tests for code that is not merged yet are marked to skip until the module exists, so `main` always passes.

## If two people share one GitHub account

It works. Pull requests and comments all appear under one name, so each comment starts with its verdict keyword (`REVIEW:` or `TEST:`) to make the author's role clear.
