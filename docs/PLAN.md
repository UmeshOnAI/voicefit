# VoiceFit — Working Plan v5

**Event:** Mistral Le Chonk London · Saturday 21 November 2026 · Fora, Chancery Lane
**Deadline:** Submission + demo video by 18:00 · Presentation: 5 minutes live
**Build budget:** 4 hours, two people, built with the Mistral Vibe coding agent
**Companion documents:** `docs/BUILD-BRIEF.md` (technical spec and tasks), `docs/UI-SPEC.md` (the page), `docs/WORKFLOW.md` (worktrees and pull requests), `docs/agents/` (agent roles), `docs/TASKS.md` (live task board). This plan covers what and why.
**Supersedes:** v4. Change from v4: two people instead of three, and a defined agent team (section 6).

**The line to remember:** *VoiceFit remembers what "last time" means, and how you felt.*

**Pitch:** *"You walk into the gym feeling flat. You ask: 'I'm feeling low today, what should I do?' VoiceFit looks at every low day you've logged and says deadlifts, because that's where you still hit your numbers. Between sets you just talk: 'RDLs, same weight as last time. Five, five, and five… actually, six on the last set.' Voxtral 3 hears the shorthand and the correction, a Mistral agent on Le Chonk looks up what 'last time' was, and the coach answers out loud, pleased: 'Logged. Sixteen reps at 80 kilos. That's one more than last time.'"*

---

## 1. What changed from v3

| Area | v3 | v4 | Why |
|---|---|---|---|
| When you log | Between sets | Between sets **or** one recap at the end, same mic, no mode switch | A recap makes the agent chain several lookups and saves in one turn: a richer trace for the jury |
| Mood | — | Low / active / pumped, spoken naturally, stored with each session | Gives the product an angle beyond logging |
| Tools | `get_last_session`, `log_session` | + `get_mood_history` | The agent has a second reason to query history |
| Voice tones | Pleased, neutral | + calm, used on low-mood days | A change of voice the jury can hear within one demo |
| French run | Demo beat | Try if time allows; not in the demo | Makes room for the mood beat |
| Competitor analytics | — | Pitch only (section 8) | Jury scores use of Mistral models, not analytics depth |
| Calendar matching | — | Pitch only (section 8) | A mocked calendar would look fake to engineers |
| Who builds | Unspecified | Mistral Vibe, from the build brief | Hackathon rule |

## 2. Prize alignment

- **Track_01 (Vibe + Le Chonk):** built end to end with Mistral Vibe; the reasoning runs on `mistral-large-4`. Keep two concrete Vibe moments to mention (for example: it generated the replay test transcripts; it wrote the comparison logic and its tests).
- **Bonus_02 (Agents):** a Mistral Agent chooses between three tools, asks when information is missing, and chains calls for a multi-exercise recap. The on-screen trace shows the real calls. We chose Agents over Workflows because a ten-second interaction does not need durable execution; say so.
- **Special_03 (Voxtral):** transcription with `context_bias` for gym shorthand; speech in three tones driven by the result.

## 3. What the product does

1. **Ask by mood.** "I'm feeling low today, what should I do?" The agent looks up past sessions with that mood and answers from counted outcomes.
2. **Log by voice between sets.** One exercise, references to "last time" resolved from history, spoken corrections applied.
3. **Or log by voice at the end.** Several exercises in one utterance; the agent saves each.
4. **Hear the result.** One or two sentences, in a tone that fits: pleased when you beat last time, calm on a low day, neutral otherwise.
5. **See the proof.** Previous and new rows side by side, and the tool trace.

**What "worked" means (computed in code, never by the model):** a session is compared with the previous session of the same exercise. Heavier weight, or the same weight with more total reps, is **beat**. Same weight and same reps is **held**. Anything else is **dropped**.

## 4. Mood, scoped

- **Capture:** spoken ("feeling low", "full of energy"). The agent maps it to `low`, `active` or `pumped`. Three chips on screen show the current mood and correct it with a tap.
- **Storage:** one mood value on each saved session.
- **Use:** `get_mood_history(mood)` returns, per exercise, how many sessions were logged in that mood and how many were held or beaten.
- **Limits to state honestly:** it runs on seeded history, it suggests which lift to pick, and it does not write a programme. Mood comes from the user's words, not from analysing their voice.

## 5. Seeded story

The seed (exact rows in the brief) is built so that:

- The last Romanian deadlift session is **80 kg · 5, 5, 5**.
- On **low** days, Romanian deadlifts were held or beaten **3 times out of 4**; bench press dropped **3 times out of 3**.
- Overhead press has **no history**, for the clarification case.

Seeded rows are labelled on screen, and a Reset button restores them.

## 6. Roles and four-hour plan

### The agent team

| Agent | Job | Worktree |
|---|---|---|
| Coordinator | Owns `docs/TASKS.md`, hands out tasks in order, watches the clock, merges pull requests | main checkout |
| Coder (core) | Tasks 0, 1, 2, 3, 5, 6: backend, tools, voice, agent | `coder` |
| Coder (ui) | Task 4: the page, built against the mock response | `coder-ui` |
| Reviewer | Reads every pull request against the brief | `reviewer` |
| Tester | Writes tests from the contracts ahead of the code; runs every pull request | `tester` |

The team is one coordinator, one coder role, one reviewer and one tester. The coder role runs as two instances for the first 90 minutes because a single coder working through seven tasks in sequence does not fit in four hours. The two instances own different files, so they cannot collide.

### The two people

- **Person 1 — build lead.** Operates the coordinator and the core coder. Owns the API key and Task 0.
- **Person 2 — quality and demo lead.** Operates the ui coder, the reviewer and the tester. Does the work only a human can: recording test clips, speaking to the app, the second-speaker test, the video and the pitch.

### Four-hour plan

Task numbers refer to the brief.

| Elapsed | Person 1 | Person 2 |
|---|---|---|
| 0:00–0:25 | Coordinator opens the board. Core coder: Task 0 (prove key, model IDs, parameters). | Record three test clips. Tester: write tests for Tasks 1 and 2 from the contracts. Ui coder: start Task 4. |
| 0:25–1:30 | Core coder: Task 1, then Task 2, then Task 3, one pull request each. | Ui coder: finish Task 4. Reviewer and tester on each pull request as it opens. Tester: write `scripts/replay.py`. |
| 1:30–2:30 | Core coder: Task 5 (agent and `/api/turn`). | Review and test Task 5. Point the page at the live endpoint. Speak the test sentences. |
| 2:30–3:10 | Core coder: Task 6 fixes, tones, recap and mood cases. | Tester: full replay run. Second-speaker test. Record the first clean take. |
| 3:10–4:00 | Feature freeze: README, rehearsal, submit. | Submission video, audio check on a second device. |

**Exit criterion at 2:30:** a teammate speaks the deadlift sentence; exactly one session is saved with [5, 5, 6]; the spoken comparison matches the screen.

**If there is a fifth hour:** five unfamiliar utterances from people outside the team, and report the real result to the jury.

**Owner checks (things I will hold the build to):**

- Task 0 results are written down before anyone builds on a model ID.
- The comparison and mood counts come from tool code, and the reply states only those numbers.
- Nothing is added after 3:10.

## 7. Demo script (5 minutes)

1. **Hook (20s):** "Fitness apps know your heart rate. None of them know you had a rough day. Watch." Start talking to the app.
2. **Mood (45s):** "I'm feeling low today, what should I do?" Calm voice: deadlifts, three of four low days held or beaten; bench dropped every time.
3. **The moment (50s):** the deadlift sentence with the correction. Two rows on screen; pleased voice: "one more than last time."
4. **Judge's number (50s):** Reset. A judge picks the last-set reps; run it again.
5. **Trace (35s):** open it. "It looked up last time, then saved. The arithmetic is ours, not the model's."
6. **Recap (40s):** "Also did bench, 62.5 kilos, eight, seven, seven, and squats same as last time, five, five, five." Two saves from one sentence.
7. **Who did what (40s):** "Voxtral 3 for transcription with context bias and for a voice with three tones. A Mistral Agent on Mistral Large 4 choosing between three tools: that is our Agents bonus. Every line was built with Vibe."
8. **Close (20s):** edge and roadmap lines from section 8.

The no-history clarification ("What weight did you use?") goes in the video and is ready for questions.

## 8. Pitch-only material

**Edge (say in the close, about 10 seconds):** "Wearables score your body from sensors. Lifting apps store your sets. Almost none capture how you felt in your own words, because typing it is a chore. Voice makes it free, and that is the data we coach from."

Named comparisons (Whoop, Oura, Garmin for sensor-based readiness; Strong, Hevy, Fitbod for set logging) come from general knowledge and were not checked today. Verify before putting any name on a slide, or keep the claim generic as above.

**Roadmap (one sentence):** "Next, the same agent gets a calendar tool, so a day of back-to-back meetings and a low mood gets a different session from a free afternoon."

Neither item appears in the app.

## 9. Risks and mitigations

- **Vibe on our machines:** native Windows is supported per the docs (install steps in `docs/WORKFLOW.md`). Install it and the GitHub CLI on both machines before the clock starts.
- **Person 2 is operating three agents:** reviewer and tester run one short prompt per pull request; if the queue backs up, Person 1 triggers the reviewer for ui pull requests.
- **Model IDs or parameters differ from the docs:** Task 0 exists for this.
- **Agents SDK (public preview) blocks progress:** falling back to chat completions with function calling keeps the demo but gives up the Agents bonus. Allow 30 minutes before switching, and say plainly which was used.
- **Live judge run fails on noise or accent:** the typed box is on screen; type the sentence and continue.
- **Long recap is mis-heard:** keep the demo recap to two exercises; rehearse it.
- **Three tone settings unavailable in TTS:** fall back to one voice and cut the claim from the pitch.
- **Mood advice sounds like a health claim:** the reply states counts from the log and a suggestion, nothing more.
- **Scope creep:** no charts, no calendar, no auth, no fourth tool.

## 10. Submission checklist

- [ ] Video: mood question, the moment, a changed number, the trace, a recap, the no-history question
- [ ] Video audio checked on a second device
- [ ] Submitted before 18:00
- [ ] README: architecture, how to run, where Voxtral, the Agent and Vibe were used, real test results
- [ ] Pitch rehearsed inside 5 minutes
- [ ] API key not committed
