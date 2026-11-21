# VoiceFit — Interface Specification

The page is one screen, shown on a projector to a jury. It must make three things obvious from the back of a room: what was heard, what was saved compared with last time, and what the agent did.

Files: `static/index.html`, `static/app.js`, `static/style.css`, `static/mock-turn.json`. No frameworks, no build step, no external scripts or fonts.

## Wireframe

Desktop width (1280 px and up). Two columns under the header.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ VoiceFit                                               [ Reset demo ]    │
├───────────────────────────────────┬──────────────────────────────────────┤
│                                   │  SESSIONS                            │
│            ( ● MIC )              │  Romanian deadlift                   │
│          Tap to speak             │  ┌────────────────────────────────┐  │
│                                   │  │ Today    80 kg  5 · 5 · 6  16  │  │
│  How you feel                     │  │          ▲ BEAT  +1 rep   NEW  │  │
│  [ Low ] [ Active ] [ Pumped ]    │  ├────────────────────────────────┤  │
│                                   │  │ 3 d ago  80 kg  5 · 5 · 5  15  │  │
│  HEARD                            │  │                         seed   │  │
│  "RDLs, same weight as last       │  │ 7 d ago  80 kg  5 · 4 · 4  13  │  │
│   time. Five, five, and five…     │  │ 10 d ago 80 kg  5 · 5 · 5  15  │  │
│   actually, six on the last set." │  └────────────────────────────────┘  │
│                                   │                                      │
│  COACH                     ♪      │  ▸ TOOL TRACE (2 calls)              │
│  "Logged. Sixteen reps at 80      │    1 get_last_session  rdls     4 ms │
│   kilos. That's one more than     │      → 80 kg · 5,5,5                 │
│   last time."                     │    2 log_session  80 kg 5,5,6   6 ms │
│                                   │      → saved · beat · +1             │
│  [ type instead…          ][Send] │                                      │
└───────────────────────────────────┴──────────────────────────────────────┘
```

Below 900 px the right column moves under the left one.

## Elements

| id | Element | Behaviour |
|---|---|---|
| `mic-btn` | Round button, at least 120 px | Click toggles recording. Space bar does the same when the text box is not focused. |
| `status` | Line under the mic | Shows the current state label (see States). |
| `mood-low`, `mood-active`, `mood-pumped` | Three chips | The chip matching the last turn's `mood` is highlighted. Clicking a chip calls `POST /api/mood` and highlights it. No chip highlighted when mood is null. |
| `heard` | Text block | `transcript` from the last turn, in quotes. |
| `coach` | Text block | `reply_text` from the last turn. A small replay control plays the audio again. |
| `coach-audio` | `<audio>` element | Plays automatically when a turn arrives with audio. |
| `text-input`, `send-btn` | Text box and button | Sends the typed text as `transcript`. Enter key sends. Always visible. |
| `sessions` | One card per exercise | See Sessions. |
| `trace` | `<details>` element | Closed by default. Summary shows the number of calls. See Trace. |
| `reset-btn` | Button, top right | Calls `POST /api/reset`, clears `session_id`, clears Heard, Coach and Trace, reloads sessions. |
| `error` | Banner under the header | Hidden unless an error is showing. |

## States

Exactly one state at a time. The mic button colour and `status` text change with it.

| State | `status` text | Mic button | Enters when | Leaves when |
|---|---|---|---|---|
| `idle` | Tap to speak | Neutral | Page load; reply finished | Mic clicked, or text sent |
| `listening` | Listening… | Red, pulsing | Mic clicked | Mic clicked again, or 30 seconds pass |
| `thinking` | Thinking… | Disabled, spinner | Audio or text posted | Response arrives |
| `speaking` | (empty) | Disabled | Audio starts playing | Audio ends, or there is no audio |
| `error` | Tap to try again | Neutral | Any failure | Next action |

While `thinking`, the mic, Send, chips and Reset are disabled.

## Recording

- `navigator.mediaDevices.getUserMedia({audio: true})`, then `MediaRecorder` with `audio/webm;codecs=opus` if supported, otherwise the browser default.
- On stop, post `multipart/form-data` to `/api/turn` with `audio` (file name `clip.webm`) and `session_id` if one is held.
- Recordings shorter than 0.5 seconds are discarded without a request.
- Keep `session_id` from each response in a variable and send it on the next turn.

## Sessions

- On page load, show one card for `romanian_deadlift` from `GET /api/sessions?exercise=romanian_deadlift&limit=4`.
- After a turn with `saved_sessions`, show one card per saved exercise, fetched with `limit=4`, in the order saved.
- After a turn with no saves, leave the cards as they are.

Each row shows: relative day ("Today", "3 d ago"), weight in kg to one decimal with trailing `.0` removed, reps separated by `·`, and total reps.

- The row whose `id` is in `saved_sessions` is highlighted and tagged **NEW**, with an outcome badge:

| outcome | Badge | Colour |
|---|---|---|
| `beat` | ▲ BEAT, plus "+N reps" when `delta_reps` is not null | Green |
| `held` | ● HELD | Blue |
| `dropped` | ▼ DROPPED, plus "−N reps" when `delta_reps` is not null | Amber |
| `first` | ★ FIRST | Grey |

- Rows with `is_seed` true carry a small "seed" tag.
- If a row has a mood, show it as a small label.

## Trace

One numbered entry per item in `trace`, in order:

- Line 1: tool name, a compact rendering of `args`, and `ms`.
- Line 2: `→` and a compact rendering of `result`.
- Clicking an entry expands the full JSON of `args` and `result`.

Compact renderings:

| Tool | Args | Result |
|---|---|---|
| `get_last_session` | the `exercise` string | `80 kg · 5,5,5`, or `no history`, or `unknown exercise` |
| `log_session` | `80 kg 5,5,6`, plus the mood if given | `saved · beat · +1`, or `not saved · <error>` |
| `get_mood_history` | the mood | `<name> 3/4 · <name> 0/3`, top three exercises |

## Errors

| Situation | Message in `error` banner |
|---|---|
| Microphone permission denied or no microphone | "Microphone unavailable. Type your entry below." |
| `/api/turn` returns a non-200 status or the network fails | "Could not reach VoiceFit. Try again or type your entry." |
| Response has `audio_base64` null | No banner. Show the text reply and skip playback. |
| Empty transcript returned | "Didn't catch that. Try again." |

The banner disappears on the next successful turn.

## Look

- Dark background, light text, one accent colour for the mic.
- Minimum sizes at 1280 px width: Heard and Coach text 24 px, session rows 22 px, labels 14 px uppercase, trace 16 px monospace.
- Contrast ratio at least 4.5 to 1 for all text.
- The highlighted new row is the most prominent thing on the right column.
- No animations other than the mic pulse and the spinner.

## Mock response

`static/mock-turn.json` holds the example below. Opening the page as `index.html?mock=1` loads this file in place of calling `/api/turn`, and loads session rows from the `mock_sessions` key in place of `/api/sessions`, so the page can be built and reviewed without a backend.

```json
{
  "turn_id": "mock-turn-1",
  "session_id": "mock-session",
  "transcript": "RDLs, same weight as last time. Five, five, and five… actually, six on the last set.",
  "reply_text": "Logged. Sixteen reps at 80 kilos. That's one more than last time.",
  "tone": "pleased",
  "audio_base64": null,
  "audio_mime": "audio/mpeg",
  "mood": "low",
  "saved_sessions": [
    {"saved": true, "session_id": 20, "exercise_id": "romanian_deadlift",
     "exercise_name": "Romanian deadlift", "weight_kg": 80.0, "reps": [5, 5, 6],
     "total_reps": 16, "mood": "low",
     "previous": {"performed_at": "2026-11-18T10:00:00Z", "weight_kg": 80.0,
                  "reps": [5, 5, 5], "total_reps": 15},
     "outcome": "beat", "delta_reps": 1}
  ],
  "trace": [
    {"tool": "get_last_session", "args": {"exercise": "rdls"},
     "result": {"found": true, "exercise_id": "romanian_deadlift",
                "exercise_name": "Romanian deadlift",
                "performed_at": "2026-11-18T10:00:00Z", "weight_kg": 80.0,
                "reps": [5, 5, 5], "total_reps": 15, "mood": "active"},
     "ms": 4},
    {"tool": "log_session",
     "args": {"exercise": "rdls", "weight": 80, "unit": "kg", "reps": [5, 5, 6], "mood": "low"},
     "result": {"saved": true, "session_id": 20, "outcome": "beat", "delta_reps": 1},
     "ms": 6}
  ],
  "mock_sessions": {
    "romanian_deadlift": [
      {"id": 20, "performed_at": "2026-11-21T14:00:00Z", "weight_kg": 80.0, "reps": [5, 5, 6], "total_reps": 16, "mood": "low", "is_seed": false},
      {"id": 8, "performed_at": "2026-11-18T10:00:00Z", "weight_kg": 80.0, "reps": [5, 5, 5], "total_reps": 15, "mood": "active", "is_seed": true},
      {"id": 7, "performed_at": "2026-11-14T10:00:00Z", "weight_kg": 80.0, "reps": [5, 4, 4], "total_reps": 13, "mood": "low", "is_seed": true},
      {"id": 6, "performed_at": "2026-11-11T10:00:00Z", "weight_kg": 80.0, "reps": [5, 5, 5], "total_reps": 15, "mood": "low", "is_seed": true}
    ]
  }
}
```

## Acceptance checks

1. `index.html?mock=1` shows the wireframe content: transcript, reply, a highlighted NEW row with ▲ BEAT +1 rep, the Low chip highlighted, three seed rows, and a trace summary reading "2 calls".
2. Expanding the trace shows both calls with compact lines; clicking one shows its JSON.
3. Clicking the mic moves through `listening` and `thinking` and produces a non-empty audio blob (log its size to the console).
4. Typing a sentence and pressing Enter posts `transcript` to `/api/turn`.
5. Denying microphone permission shows the banner and leaves the text box usable.
6. At 1280 × 720 everything in the wireframe is visible without scrolling.
7. Reset clears Heard, Coach and Trace and reloads the sessions card.
