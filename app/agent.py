"""VoiceFit agent (Task 5): the Mistral Agent over app/tools.py.

Every SDK name here comes from NOTES.md (verified live in Task 0), not from
memory: model "mistral-large-4", @agents.tool decorated functions at module
scope with fully typed parameters, agents.Agent(tools=[...]), and sessions
started with start_session() / rebound with agent.session(id) and run with
session.run(msg) (plain agent.run() closes the session after one turn).

The three SDK tools are thin async wrappers around the pure functions in
app/tools.py; blocking sqlite work goes through asyncio.to_thread.

Gotcha found live (Task 5 check): for a session started with start_session()
the SDK runs tool handlers in a context derived from the request, so the
TRACE / TURN_ID context vars propagate. For a session rebound with
agent.session(id) the SDK's worker runs in its own older context and the
context vars are lost — the trace came back empty on continued turns. So
run_turn also hands the current (turn_id, trace) to the wrappers through the
module globals below, and every tool call re-sets the context vars inside its
thread before calling tools.py. The handoff is process-global, which is fine
here: /api/turn handles one lifter at a time, sequentially.
"""

import asyncio

from mistralai import agents

from . import tools

# Model ID verified in NOTES.md (Task 0).
AGENT_MODEL = "mistral-large-4"

# Current turn handoff for the tool wrappers (see module docstring).
_ACTIVE_TURN_ID: str | None = None
_ACTIVE_TRACE: list | None = None


def _invoke(fn, *args):
    """Call a tools.py function in a worker thread with TRACE/TURN_ID set,
    regardless of which context the SDK ran the tool handler in."""
    trace = _ACTIVE_TRACE if _ACTIVE_TRACE is not None else tools.TRACE.get()
    turn_id = _ACTIVE_TURN_ID if _ACTIVE_TURN_ID is not None else tools.TURN_ID.get()
    trace_token = tools.TRACE.set(trace)
    turn_token = tools.TURN_ID.set(turn_id)
    try:
        return fn(*args)
    finally:
        tools.TRACE.reset(trace_token)
        tools.TURN_ID.reset(turn_token)


@agents.tool
async def get_last_session(exercise: str) -> dict:
    """Look up the most recent saved session for an exercise, by name or alias (case-insensitive). Returns found, weight_kg, reps, total_reps, mood, or an error."""
    return await asyncio.to_thread(_invoke, tools.get_last_session, exercise)


@agents.tool
async def log_session(exercise: str, weight: float, unit: str, reps: list[int], mood: str | None = None) -> dict:
    """Save one exercise session: exercise name or alias, weight with unit 'kg' or 'lb', reps as a list of ints (one per set), and an optional mood: low, active or pumped. Returns saved, outcome vs the previous session, total_reps, or an error."""
    return await asyncio.to_thread(_invoke, tools.log_session, exercise, weight, unit, reps, mood)


@agents.tool
async def get_mood_history(mood: str) -> dict:
    """How past sessions went in one mood ('low', 'active' or 'pumped'): counts per exercise and a suggested exercise id."""
    return await asyncio.to_thread(_invoke, tools.get_mood_history, mood)


# Verbatim from docs/BUILD-BRIEF.md, section "Agent / Instructions".
INSTRUCTIONS = """You are VoiceFit. A lifter speaks to you in the gym and you receive the transcript.
They may log one exercise between sets, log several exercises in one go at the end,
tell you how they feel, or ask what to do.

Logging:
- Work out each exercise, its weight and unit, and the reps for every set as a list.
- If they refer to a previous session ("same as last time", "same weight"), call
  get_last_session for that exercise first and use its weight in kg.
- Apply spoken corrections: "five, five, and five... actually six on the last set"
  means [5, 5, 6].
- Never guess a weight or a unit. If either is missing and history does not supply
  it, ask one short question and do not call log_session for that exercise.
- Call log_session once per exercise.

Mood:
- If they say how they feel, map it to exactly one of: low, active, pumped.
  Pass it as mood on log_session calls in this conversation.
- If they ask what to do given how they feel, call get_mood_history with that mood.
  Recommend the suggested exercise and state the counts it returned, for example
  "held or beat your numbers 3 of 4 times". If there is no suggestion, say there is
  not enough history yet.

Replying:
- One or two short sentences, written to be spoken aloud. No lists, no symbols.
- State only numbers that a tool returned. Do not calculate anything yourself.
- After logging, say the total reps and weight, and the comparison with last time
  if there is one.
- Reply in the language the lifter used.
- Do not give medical or injury advice.
"""

_agent: "agents.Agent | None" = None

# Session ids started by this server process. /api/reset drops them, so a
# client sending a pre-reset session_id gets a fresh session, not a dead one.
_active_sessions: set[str] = set()


def _get_agent() -> "agents.Agent":
    """Build the agent lazily so importing this module needs no API key."""
    global _agent
    if _agent is None:
        _agent = agents.Agent(
            model=AGENT_MODEL,
            instructions=INSTRUCTIONS,
            tools=[get_last_session, log_session, get_mood_history],
        )
    return _agent


async def run_turn(
    transcript: str,
    session_id: str | None = None,
    turn_id: str | None = None,
    trace: list | None = None,
) -> tuple[str, str]:
    """Run one agent turn. Starts a new session when session_id is missing (or was
    dropped by /api/reset) and continues the existing one otherwise.

    turn_id and trace are the current /api/turn request's; they are handed to
    the tool wrappers so every tool call lands in the request's trace even for
    rebound sessions (see module docstring).

    Returns (reply_text, session_id) — send session_id back on the next turn.
    """
    global _ACTIVE_TURN_ID, _ACTIVE_TRACE
    agent = _get_agent()
    if session_id and session_id in _active_sessions:
        session = agent.session(session_id)
    else:
        session = await agent.start_session()
    _ACTIVE_TURN_ID, _ACTIVE_TRACE = turn_id, trace
    try:
        result = await session.run(transcript)
    finally:
        _ACTIVE_TURN_ID, _ACTIVE_TRACE = None, None
    _active_sessions.add(result.session_id)
    return (getattr(result, "text", "") or ""), result.session_id


def drop_sessions() -> int:
    """Forget all agent sessions started by this process. Returns how many."""
    n = len(_active_sessions)
    _active_sessions.clear()
    return n
